import chromadb
import shutil
import os

print("⚠️ กำลังเตรียมล้างสมอง AI...")

try:
    # วิธีที่ชัวร์ที่สุดในการเคลียร์ ChromaDB คือการลบไฟล์ฐานข้อมูลข้างในทิ้ง
    db_path = "./ai_memory_palace"
    
    if os.path.exists(db_path):
        # ลบโฟลเดอร์ทิ้ง
        shutil.rmtree(db_path)
        print("🗑️ ลบความทรงจำเก่าสำเร็จ!")
        
        # สร้างโฟลเดอร์ใหม่รอไว้
        os.makedirs(db_path)
        print("✨ สร้างพื้นที่สมองใหม่ว่างเปล่าเรียบร้อยแล้ว!")
        print("\n👉 อย่าลืมรันคำสั่ง 'python -m mempalace init ./ai_memory_palace --no-llm' อีกครั้งก่อนรันเซิร์ฟเวอร์นะครับ")
    else:
        print("ไม่พบฐานข้อมูลความจำ (AI อาจจะยังไม่มีความจำเลย)")
        
except Exception as e:
    print(f"เกิดข้อผิดพลาดในการล้างความจำ: {e}")