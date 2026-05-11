import re
import time
import uuid
import chromadb

# ==========================================
# ⚙️ CONFIGURATIONS & CONSTANTS (ตั้งค่าคงที่)
# ==========================================
# ขีดจำกัดการเตือนของร่างกาย
WARN_HUNGER = 0
WARN_ENERGY = 100
WARN_LONELY = 0

# คลังคำศัพท์สำหรับระบบไขสันหลัง (Reflex Keywords)
AHA_KEYWORDS = ["completed successfully", "finished", "completed.", "delicious", "well", "entertaining", "เสร็จแล้ว", "อร่อย", "สบายดี", "สนุก"]
EH_KEYWORDS = ["don't remember", "cannot", "too far", "stuck", "too much", "bloated", "not understand", "จำพิกัด", "ไม่ได้", "ไม่เข้าใจ", "กีดขวาง", "ไกลเกินไป", "มันอยู่ตรงไหนนะ", "จำตำแหน่งไม่ได้"]

# คลังคำสั่งที่ร่างกายทำได้ (Action Validator)
VALID_COMMANDS = ["MoveDir", "Approach", "Interact", "Turn"]

# คลังคำนามธรรมที่ร่างกายไม่เข้าใจ (Abstract Concept Detector)
ABSTRACT_KEYWORDS = ["unknown", "nearest", "closest", "point", "any", "something", "object"]


# ==========================================
# 📝 PROMPT TEMPLATES (คู่มือการทำงานของ AI)
# ==========================================
SYSTEM_PERSONA = """[SYSTEM RULE: You're a character in a simulated, game-like world. You're cognitively flexible: embracing good surprises, but confused by illogical events. You're completely alone. All perceived inputs are internal.]"""

ACTION_MANUAL = """[Available Actions]
- MoveDir(direction, distance): e.g., MoveDir(forward, 5)
- Approach(object_name): e.g., Approach(Fridge)
- Interact(object_name): e.g., Interact(Bed) - within 3m
- Turn(direction, degrees): e.g., Turn(right, 360)"""


# ==========================================
# 🧠 STATE VARIABLES (สมุดจดความจำระยะสั้น)
# ==========================================
# ประกาศตัวแปรทั้งหมดไว้ตรงนี้ เพื่อป้องกัน Attribute Error เวลารันครั้งแรก
action_queue = []
pending_evaluation = None  
recent_actions = [] 
working_error_memory = [] 
spatial_memory = {} 

# ตัวแปรสำหรับ System 2 (Scientist Mode)
experiment_loop = 0
experiment_logs = []
hypotheses_history = []
past_lessons = []

server_is_shutting_down = False  # 🌟 [เพิ่มตรงนี้] ปุ่มตัดไฟฉุกเฉิน
action_queue = []


# ==========================================
# 🏰 LONG-TERM MEMORY (วังความจำ MemPalace)
# ==========================================
AI_WING = "Agent_Core"
LESSON_ROOM = "Survival_Lessons"

# เชื่อมต่อฐานข้อมูลตอนที่ไฟล์นี้ถูกเรียกใช้ครั้งแรก
try:
    palace_client = chromadb.PersistentClient(path="./ai_memory_palace")
    ltm_vault = palace_client.get_or_create_collection(name="mempalace_drawers")
    print("✅ [Memory Core] เชื่อมต่อวังความจำ (MemPalace) ประสบความสำเร็จ!")
except Exception as e:
    ltm_vault = None
    print(f"❌ [Memory Core] ไม่สามารถเชื่อมต่อฐานข้อมูลได้: {e}")


# ==========================================
# 🛠️ MEMORY HELPERS (ฟังก์ชันผู้ช่วยจัดการความจำ)
# ==========================================
def update_spatial_memory(objects_nearby, last_feedback):
    """อัปเดตพิกัดสิ่งของที่มองเห็นลงในแผนที่ความจำ (Spatial Memory)"""
    global spatial_memory
    text_to_scan = " ".join(objects_nearby) if objects_nearby else ""
    text_to_scan += " " + last_feedback

    # ค้นหาพิกัดและบันทึก
    matches = re.finditer(r'([a-zA-Z0-9_]+)\s+at\s+\(X:\s*([-\d.]+),\s*Z:\s*([-\d.]+)\)', text_to_scan)
    for match in matches:
        obj_name = match.group(1)
        if "wall" not in obj_name.lower() and "plane" not in obj_name.lower():
            spatial_memory[obj_name] = (float(match.group(2)), float(match.group(3)))

def get_spatial_memory_text():
    """แปลงแผนที่ในหัวให้เป็นข้อความเพื่อให้ System 1 และ 2 อ่าน"""
    if not spatial_memory:
        return "ฉันจำพิกัดของอะไรไม่ได้เลย"
    return ", ".join([f"{k} (X:{v[0]:.1f}, Z:{v[1]:.1f})" for k, v in spatial_memory.items()])

def recall_past_lessons(search_query, top_k=3):
    """รื้อฟื้นความจำจาก MemPalace"""
    if not ltm_vault:
        return "ฉันนึกไม่ออกเลยว่าเคยเจอเรื่องแบบนี้ (Database Error)"
    try:
        results = ltm_vault.query(query_texts=[search_query], n_results=top_k, where={"wing": AI_WING})
        if results and results['documents'] and len(results['documents'][0]) > 0:
            return "\n".join([f"- {doc}" for doc in results['documents'][0]])
    except Exception:
        pass
    return "ฉันนึกไม่ออกเลยว่าเคยเจอเรื่องแบบนี้"

def save_lesson(extracted_lesson):
    """ฝังบทเรียนใหม่ลงใน MemPalace อย่างถาวร"""
    if not ltm_vault:
        return
    try:
        doc_id = f"lesson_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        ltm_vault.add(
            documents=[extracted_lesson], 
            metadatas=[{"wing": AI_WING, "room": LESSON_ROOM}], 
            ids=[doc_id]
        )
        
        # 🌟 [ปรับปรุง] หน้าตาการแจ้งเตือนบน Terminal
        print("\n" + "📜" * 30)
        print("✨ [MEMPALACE NOTIFICATION] ✨")
        print(f"📖 บันทึกความจำระยะยาวใหม่:")
        print(f"   > \033[92m{extracted_lesson}\033[0m") # แสดงเป็นสีเขียว
        print("📜" * 30 + "\n")
        
    except Exception as e:
        print(f"⚠️ บันทึกความจำล้มเหลว: {e}")


# ==========================================
# 🩸 SENSORY HELPERS (ฟังก์ชันประมวลผลร่างกาย)
# ==========================================
def translate_body_state(energy, hunger, loneliness):
    """
    รับค่าตัวเลขของร่างกาย แล้วแปลงเป็นข้อความ (Body Needs & Alert Text)
    เพื่อให้สมองทุกส่วนเรียกใช้ได้โดยไม่ต้องเขียนลอจิกซ้ำซ้อน
    """
    urges = {"Sleepiness": 100 - energy, "Hunger": hunger, "Loneliness": loneliness}
    active_urges = {k: v for k, v in urges.items() if v > 0}
    
    if active_urges:
        body_needs = ", ".join([f"{act} ({score:.0f}%)" for act, score in sorted(active_urges.items(), key=lambda i: i[1], reverse=True)])
    else:
        body_needs = "All needs are satisfied. I feel completely fine."

    alerts = []
    if hunger < WARN_HUNGER: alerts.append(f"Too full ({hunger:.0f})")
    if energy > WARN_ENERGY: alerts.append(f"Feeling restless ({energy:.0f})")
    if loneliness < WARN_LONELY: alerts.append(f"Want to be alone ({loneliness:.0f})")
    
    alert_text = ", ".join(alerts) if alerts else "Normal"
    
    return body_needs, alert_text

def get_action_history_text():
    """ดึงประวัติการกระทำ 3 ก้าวล่าสุดออกมาเป็นข้อความพร้อมใช้งาน"""
    if recent_actions:
        labels = ["Latest", "Previously", "Before that"]
        return "\n    ".join([f"- {labels[i]}: {act}" for i, act in enumerate(reversed(recent_actions)) if i < len(labels)])
    return "- Just woke up. Haven't done anything yet."

def record_action(new_action):
    """จดจำคำสั่งล่าสุดลง Action History (ย้ายมาจาก api_server)"""
    global recent_actions
    recent_actions.append(new_action)
    if len(recent_actions) > 3:
        recent_actions.pop(0)