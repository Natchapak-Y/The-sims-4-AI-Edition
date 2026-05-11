import re
import time
from langchain_ollama import OllamaLLM
import memory_core  # pyright: ignore[reportMissingImports]
import sys
import threading

MODEL_NAME = "gemma4:e2b" 
DEBUG_PROMPT = True  

llm = OllamaLLM(model=MODEL_NAME)

def stream_and_get_response(prompt: str, title: str) -> str:
    if DEBUG_PROMPT:
        print("\n" + "📦"*25)
        print(f"📥 [DEBUG PROMPT] กำลังส่งข้อมูลนี้ให้ AI ({title}):")
        print("\033[93m" + prompt.strip() + "\033[0m") 
        print("📦"*25 + "\n")

    print(f"\n{title}:")
    is_thinking = True

    def loading_animation():
        thoughts = ["กำลังเชื่อมต่อเส้นประสาทเทียม", "กำลังทบทวนความจำระยะสั้น", "กำลังประเมินสถานการณ์แวดล้อม", "กำลังจำลองทางเลือกในหัว"]
        dot_states = ["", ".", "..", "..."]
        dot_idx = 0
        start_time = time.time()
        while is_thinking:
            elapsed = time.time() - start_time
            text_index = int(elapsed / 1.5)
            base_text = thoughts[text_index % len(thoughts)]
            dots = dot_states[dot_idx % 4]
            dot_idx += 1
            sys.stdout.write(f"\r\033[90m   > {base_text}{dots}\033[0m".ljust(60))
            sys.stdout.flush()
            for _ in range(4): 
                if not is_thinking: break
                time.sleep(0.1)

    anim_thread = threading.Thread(target=loading_animation)
    anim_thread.start()
    response = ""
    first_chunk = True

    try:
        for chunk in llm.stream(prompt):
            # 🌟 [เพิ่มโค้ดส่วนนี้!] เช็คสวิตช์ตัดไฟทุกๆ เสี้ยววินาทีที่พ่นคำออกมา
            if memory_core.server_is_shutting_down:
                print("\n⚠️ [System] ถูกสั่งยกเลิกความคิดฉุกเฉิน!")
                break
                
            if first_chunk:
                is_thinking = False
                anim_thread.join()
                sys.stdout.write("\r\033[K\033[36m") 
                sys.stdout.flush()
                first_chunk = False
            sys.stdout.write(chunk); sys.stdout.flush()
            response += chunk
    except Exception as e: print(f"\n[Error]: {e}")
    finally:
        is_thinking = False
        if anim_thread.is_alive(): anim_thread.join()
    print("\033[0m\n" + "-"*50) 
    return response.strip()


def think_fast(stats: dict, current_x: float, current_z: float, objects_nearby: list, last_feedback: str) -> dict:
    start_time = time.time()

    memory_core.update_spatial_memory(objects_nearby, last_feedback)
    spatial_memory_text = memory_core.get_spatial_memory_text()

    if not getattr(memory_core, 'action_queue', []): memory_core.action_queue = []
    if not getattr(memory_core, 'current_expectation', ""): memory_core.current_expectation = "ไม่มีความคาดหวัง"

    # 🌟 ดึงค่าจาก Dynamic Stats และใช้ฟังก์ชันแปลผลของ memory_core
    energy = stats.get("energy", 100.0)
    hunger = stats.get("hunger", 0.0)
    loneliness = stats.get("loneliness", 0.0)
    body_needs, alert_text = memory_core.translate_body_state(energy, hunger, loneliness)

    # =================================================================
    # 🔍 1. โหมดประเมินผล (Aha/Eh Layer & Reflex System)
    # =================================================================
    print("\n" + "="*60)
    if getattr(memory_core, 'pending_evaluation', None) and last_feedback:
        past_step = memory_core.pending_evaluation
        past_action = past_step["action"]
        past_hyp = past_step["hypothesis"]

        # 🌟 ระบบคำนวณส่วนต่างอัตโนมัติ (คำนวณเฉพาะค่าที่มีการเปลี่ยนแปลง)
        pre_state = past_step.get("pre_state", {})
        changes = [f"{k.capitalize()} {stats[k] - pre_state[k]:+.0f}" for k in stats if k in pre_state and stats[k] - pre_state[k] != 0]
        state_change = f"({', '.join(changes)})" if changes else "(ไม่มีการเปลี่ยนแปลง)"

        # 🌟 [จุดที่แก้ไข] โหมดคุ้มกัน System 2: ต้องรอคิวว่างก่อนค่อยเรียก System 2
        if getattr(memory_core, 'experiment_loop', 0) > 0:
            # 🚩 เช็คก่อนว่า "งานในคิว" ของแผนการทดลองจบหรือยัง?
            if not memory_core.action_queue:
                print(f"🧪 [System 1 Bypass] แผนทดลองจบแล้ว! ส่งไม้ต่อกลับไปวิเคราะห์รอบที่ {memory_core.experiment_loop}...")
                memory_core.pending_evaluation = None
                detailed_thought = f"เป้าหมายทดลอง: '{past_hyp}' -> สั่ง: '{past_action}' -> ผลลัพธ์: '{last_feedback}' -> ผลกระทบต่อร่างกาย: {state_change}"
                return {"action": "CALL_SYSTEM2", "thought": detailed_thought}
            else:
                # 🏃 ถ้าในคิวยังมีงานเหลือ (เช่น เหลือ Interact) ให้ปล่อยผ่านไปทำงานต่อ
                print(f"🏃 [System 1 Continue] แผนทดลองยังเหลืออีก {len(memory_core.action_queue)} ขั้นตอน... กำลังดำเนินการต่อ")
                # (ไม่ต้องมี return อะไรตรงนี้ เพื่อให้โค้ดไหลลงไปดึงคิวงานถัดไปใน Execution Layer ด้านล่าง)

        eval_state = ""
        learned_text = "-"
        is_reflex = False
        feedback_lower = last_feedback.lower()
        
        # 🌟 ดึงคีย์เวิร์ดจาก memory_core
        if any(k in feedback_lower for k in memory_core.AHA_KEYWORDS):
            eval_state = "AHA"
            is_reflex = True
            print("⚡ [Reflex System] ร่างกายตอบสนองอัตโนมัติ: AHA")
        elif any(k in feedback_lower for k in memory_core.EH_KEYWORDS):
            eval_state = "EH"
            is_reflex = True
            print("⚡ [Reflex System] ร่างกายตอบสนองอัตโนมัติ: EH")

        if not is_reflex:
            micro_eval_prompt = f"""
            Task: Evaluate if the Action's result matches the Expectation.
            Action: {past_action}
            Expectation: {past_hyp}
            Feedback: {last_feedback}

            Rules:
            - Reply "1. EVALUATION: AHA" if Feedback is logical or successful.
            - Reply "1. EVALUATION: EH" if Feedback indicates failure, error, or weirdness.
            - Reply "2. LEARNED: [1 short THAI sentence]" if AHA gives new insight, else "-".
            """
            eval_res = stream_and_get_response(micro_eval_prompt, "🔍 ประเมินผลลัพธ์ (Micro-LLM)")
            eval_match = re.search(r'1\.\s*(?:EVALUATION|การประเมิน):\s*(AHA|EH)', eval_res, re.IGNORECASE)
            learned_match = re.search(r'2\.\s*(?:LEARNED|สิ่งที่เรียนรู้):\s*(.*)', eval_res, re.IGNORECASE)
            eval_state = eval_match.group(1).upper() if eval_match else "AHA"
            learned_text = learned_match.group(1).strip() if learned_match else "-"

        if eval_state == "EH":
            print(f"❓ [System 1 เอ๊ะ!] สับสนกับผลลัพธ์ ล้างคิวงานและเรียก System 2...")
            memory_core.action_queue = []
            memory_core.current_expectation = "ไม่มี"
            detailed_thought = f"เป้าหมาย: '{past_hyp}' -> สั่ง: '{past_action}' -> ผลลัพธ์: '{last_feedback}' -> ผลกระทบต่อร่างกาย: {state_change}"
            memory_core.pending_evaluation = None
            return {"action": "CALL_SYSTEM2", "thought": detailed_thought}
        else:
            print(f"💡 [System 1 อ๋อ!] ผลลัพธ์รับได้ ลุยแผนต่อ!")
            if learned_text != "-" and "เป็นไปตามคาด" not in learned_text:
                # 🌟 [เพิ่มบรรทัดนี้] บันทึกลง MemPalace ทันที
                memory_core.save_lesson(f"เรียนรู้จากการกระทำ: {learned_text}")
                
                if not hasattr(memory_core, 'past_lessons'): memory_core.past_lessons = []
                memory_core.past_lessons.append(learned_text)
                if len(memory_core.past_lessons) > 5: memory_core.past_lessons.pop(0)

    # =================================================================
    # 🚦 2. โหมดวางแผน (Planning Layer)
    # =================================================================
    if not memory_core.action_queue:
        actions_text = memory_core.get_action_history_text()

        # 🌟 Prompt สะอาดขึ้นมหาศาล เพราะดึงคู่มือจาก memory_core!
        plan_prompt = f"""
        {memory_core.SYSTEM_PERSONA}
        
        [Body Status]: {body_needs} | Sensation: {alert_text}
        
        You wake up with the following memories:
        [My Current Position]: (X: {current_x:.1f}, Z: {current_z:.1f})
        [Spatial Memory]: {spatial_memory_text}
        [Action History]: 
        {actions_text}
        [Latest Body Feedback]: {last_feedback if last_feedback else "No feedback"}
        
        {memory_core.ACTION_MANUAL}
        
        [CRITICAL OUTPUT RULE]
        IMPORTANT: You MUST write your final response (PLAN and EXPECTATION) entirely in the THAI language.
        
        Plan your actions to satisfy your body's needs. Respond strictly in this 2-point format:
        1. PLAN: [Write a queue of 1-3 steps separated by -> (e.g., Turn(right, 360) -> Approach(Fridge) -> Interact(Fridge))]
        2. EXPECTATION: [What you expect to happen once this entire queue is completed. Write this in Thai]
        """

        plan_res = stream_and_get_response(plan_prompt, "🚦 โหมดสัญชาตญาณ (วางแผนล่วงหน้า)")
        
        plan_match = re.search(r'1\.\s*(?:PLAN|แผน|แผนการ):\s*(.*)', plan_res, re.IGNORECASE)
        expect_match = re.search(r'2\.\s*(?:EXPECTATION|ความคาดหวัง|คาดหวัง):\s*(.*)', plan_res, re.IGNORECASE)
        
        plan_text = plan_match.group(1).strip() if plan_match else "Turn(right, 360)"
        plan_text = plan_text.replace('[', '').replace(']', '') 
        new_expect = expect_match.group(1).strip() if expect_match else "[บัค]"
        
        valid_actions = [cmd.group(0) for cmd in re.finditer(r'[a-zA-Z0-9_]+\s*\([^)]*\)', plan_text)]
        memory_core.action_queue = valid_actions if valid_actions else ["Turn(right, 360)"]
        memory_core.current_expectation = new_expect
        print(f"📝 [System 1 วางแผนใหม่] คิวงาน: {memory_core.action_queue} | หวังว่า: {memory_core.current_expectation}")

    # =================================================================
    # 🏃‍♂️ 3. โหมดลงมือทำ (Execution Layer)
    # =================================================================
    if memory_core.action_queue:
        next_action = memory_core.action_queue.pop(0)
        
        # 🌟 บันทึกสถานะร่างการตอนนั้นเป็น stats.copy() เพื่อให้ระบบตรวจจับการเปลี่ยนแปลงอัตโนมัติทำงานได้
        memory_core.pending_evaluation = {
            "action": next_action, 
            "hypothesis": memory_core.current_expectation,
            "pre_state": stats.copy() 
        }
        
        # 🌟 ใช้ฟังก์ชันจดความจำจาก memory_core
        memory_core.record_action(next_action)
        
        action_for_body = next_action
        action_name = next_action.split('(')[0].strip()
        
        # 🌟 ดึงคลังตรวจสอบความถูกต้องจาก memory_core
        if action_name not in memory_core.VALID_COMMANDS:
            action_for_body = f"UnknownCommand({action_name})"
        else:
            if "Approach(" in next_action:
                match = re.search(r'Approach\((.+?)\)', next_action, re.IGNORECASE)
                if match:
                    target = match.group(1).strip()
                    is_abstract = re.search(r'[ก-๙]', target) or " " in target or any(kw in target.lower() for kw in memory_core.ABSTRACT_KEYWORDS)
                    if is_abstract:
                        action_for_body = f"InvalidTarget({target})"
                    else:
                        coords = next((v for k, v in memory_core.spatial_memory.items() if k.lower() == target.lower()), None)
                        action_for_body = f"ApproachPoint({coords[0]:.1f}, {coords[1]:.1f})" if coords else f"ApproachUnknown({target})"

        elapsed = time.time() - start_time
        thought = f"ฉันกำลัง {next_action} (เพราะหวังว่า {memory_core.current_expectation})"
        
        print(f"\n🎯 [System 1] คิวงานในหัวเหลือ: {len(memory_core.action_queue)}")
        print(f"👉 ส่งสัญญาณประสาทไปที่ร่างกาย: {action_for_body} (ความคิด: {next_action})")
        print(f"⏱️ ใช้เวลาประมวลผล: {elapsed:.2f} วินาที")
        print("="*60 + "\n")

        return {"action": action_for_body, "thought": thought}
    
    return {"action": "Turn(right, 360)", "thought": "ไม่รู้จะทำอะไร"}