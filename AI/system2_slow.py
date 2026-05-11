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
        thoughts = ["ตั้งสมมุติฐาน", "จำลองความน่าจะเป็น", "วิเคราะห์เชิงลึก", "ทบทวนตรรกะเดิม"]
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

def think_slow(stats: dict, current_x: float, current_z: float, objects_nearby: list, last_feedback: str, system1_thought: str = "") -> dict:
    start_time = time.time()
    
    memory_core.experiment_loop += 1
    loop_count = memory_core.experiment_loop

    print("\n" + "🧪"*20)
    print(f"🔬 [System 2] เริ่มการวิเคราะห์รอบที่ {loop_count}/3")
    print("🧪"*20)

    spatial_memory_text = memory_core.get_spatial_memory_text()
    vision_text = ", ".join(objects_nearby) if objects_nearby else "ไม่มีอะไรในระยะสายตา"
    
    exp_history = "\n".join([f"รอบที่ {i+1}: {log}" for i, log in enumerate(memory_core.experiment_logs)]) if memory_core.experiment_logs else "ยังไม่มีการทดลองก่อนหน้า"
    hyp_history_text = "\n".join([f"รอบที่ {i+1}: {h}" for i, h in enumerate(memory_core.hypotheses_history)]) if memory_core.hypotheses_history else "ยังไม่มีสมมติฐานก่อนหน้า"

    # 🌟 เรียกใช้ฟังก์ชันดึงประวัติการกระทำ และ สถานะร่างกายจาก memory_core
    actions_text = memory_core.get_action_history_text()
    energy = stats.get("energy", 100.0)
    hunger = stats.get("hunger", 0.0)
    loneliness = stats.get("loneliness", 0.0)
    body_needs, alert_text = memory_core.translate_body_state(energy, hunger, loneliness)

    if loop_count < 3:
        scientific_prompt = f"""
        {memory_core.SYSTEM_PERSONA}
        
        [Current State]
        - Vision: {vision_text}
        - My Current Position: (X: {current_x:.1f}, Z: {current_z:.1f})
        - Spatial Memory: {spatial_memory_text}
        - Action History: 
        {actions_text}
        - Latest Feedback: {last_feedback}
        - Hypotheses History:
        {hyp_history_text}
        - Experiment History: 
        {exp_history}
        - Your Doubt: {system1_thought}
        [Body Status]: {body_needs} | Sensation: {alert_text}

        {memory_core.ACTION_MANUAL}

        [Thought Loop {loop_count}]: Analyze the latest Feedback and compare it to your Experiment History. You MUST adapt your thinking. 
        
        [CRITICAL OUTPUT RULE]
        IMPORTANT: Write your final response entirely in THAI.
        
        Strictly follow this format:
        HYPOTHESES: [List 2-3 NEW or REFINED possibilities based on the latest feedback. DO NOT blindly copy the Hypotheses History. You must evolve your thought. Write in Thai]
        TEST_PLAN: [Write EXACTLY 1 sequence of Actions joined by ->. NO bullet points. NO extra text or explanations. e.g., Turn(right, 90) -> Approach(Fridge)]
        EXPECTATION: [If the chosen hypothesis is true, what exact feedback do you expect? Write in Thai]
        """
    else:
        scientific_prompt = f"""
        {memory_core.SYSTEM_PERSONA}

        [Current State]
        - Vision: {vision_text}
        - My Current Position: (X: {current_x:.1f}, Z: {current_z:.1f})
        - Spatial Memory: {spatial_memory_text}
        - Action History: 
        {actions_text}
        - Latest Feedback: {last_feedback}
        - Hypotheses History:
        {hyp_history_text}
        - Experiment History: 
        {exp_history}
        - Your Doubt: {system1_thought}
        [Body Status]: {body_needs} | Sensation: {alert_text}
        
        [Objective]: Conclude which hypothesis is most likely, score it, and save it as permanent knowledge, because you are tired of thinking.
        
        {memory_core.ACTION_MANUAL}

        [CRITICAL OUTPUT RULE]
        IMPORTANT: Write your final response entirely in THAI.
        
        Strictly follow this format:
        SUMMARY: [Briefly summarize what happened in the past 3 loops. Write in Thai]
        CONCLUSION: [Pick the best hypothesis, give a confidence score 0-100%, and explain why others scored lower. Write in Thai]
        ACTION: [Final action to finish this task or start a new one (e.g., Turn(right, 360))]
        """

    response = stream_and_get_response(scientific_prompt, f"🔬 สมองส่วนลึกวิเคราะห์ (รอบ {loop_count})")

    try:
        if loop_count < 3:
            hyp_match = re.search(r'HYPOTHESES:\s*(.*?)(?=TEST_PLAN:|$)', response, re.IGNORECASE | re.DOTALL)
            if hyp_match:
                memory_core.hypotheses_history.append(hyp_match.group(1).strip())

            plan_match = re.search(r'TEST_PLAN:\s*(.*)', response, re.IGNORECASE)
            expect_match = re.search(r'EXPECTATION:\s*(.*)', response, re.IGNORECASE)
            
            plan_text = plan_match.group(1).strip() if plan_match else "Turn(right, 360)"
            new_expect = expect_match.group(1).strip() if expect_match else "เพื่อหาคำตอบ"
            
            memory_core.experiment_logs.append(f"สั่ง {plan_text} หวังว่าจะเจอ {new_expect}")
            
            valid_actions = [cmd.group(0) for cmd in re.finditer(r'[a-zA-Z0-9_]+\s*\([^)]*\)', plan_text)]
            memory_core.action_queue = valid_actions if valid_actions else ["Turn(right, 360)"]
            memory_core.current_expectation = f"[ทดลองรอบ {loop_count}] {new_expect}"
        else:
            conclude_match = re.search(r'CONCLUSION:\s*(.*)', response, re.IGNORECASE)
            final_action_match = re.search(r'ACTION:\s*(.*)', response, re.IGNORECASE)
            
            conclusion = conclude_match.group(1).strip() if conclude_match else "ไม่สามารถสรุปได้ชัดเจน"
            final_action = final_action_match.group(1).strip() if final_action_match else "Turn(right, 360)"
            
            # 🌟 [เพิ่มบรรทัดนี้] บันทึกข้อสรุปการทดลองลง MemPalace
            memory_core.save_lesson(f"ข้อสรุปจากการทดลอง: {conclusion}")
            
            if not hasattr(memory_core, 'past_lessons'): memory_core.past_lessons = []
            memory_core.past_lessons.append(f"ข้อสรุปจากการทดลอง 3 รอบ: {conclusion}")
            
            print(f"✅ [Scientist Mode] จบการทดลอง! ข้อสรุปคือ: {conclusion}")
            
            valid_actions = [cmd.group(0) for cmd in re.finditer(r'[a-zA-Z0-9_]+\s*\([^)]*\)', final_action)]
            memory_core.action_queue = valid_actions if valid_actions else ["Turn(right, 360)"]
            
            memory_core.current_expectation = "ทำงานตามข้อสรุปใหม่"
            memory_core.experiment_loop = 0
            memory_core.experiment_logs = []
            memory_core.hypotheses_history = [] 

        next_action = memory_core.action_queue.pop(0)
        
        # 🌟 [เพิ่มโค้ดส่วนนี้!] แปะ Post-it ให้ System 1 รู้ว่าต้องส่ง Feedback กลับมาเข้าลูป 2
        memory_core.pending_evaluation = {
            "action": next_action, 
            "hypothesis": memory_core.current_expectation,
            "pre_state": stats.copy() 
        }
        
        # 🌟 ใช้ฟังก์ชันจดความจำจาก memory_core
        memory_core.record_action(next_action)
        
        action_for_body = next_action
        action_name = next_action.split('(')[0].strip()
        
        # 🌟 ดึงคลังตรวจสอบความถูกต้องจาก memory_core เหมือน System 1
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

        return {"action": action_for_body, "thought": response.replace('\n', ' | ')}

    except Exception as e:
        print(f"⚠️ [Error]: {e}")
        return {"action": "Turn(right, 360)", "thought": "สับสน ขอตั้งสติ"}