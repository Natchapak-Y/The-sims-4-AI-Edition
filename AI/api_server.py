from fastapi import FastAPI # pyright: ignore[reportMissingImports]
from pydantic import BaseModel
from typing import List, Dict  
import uvicorn
import memory_core  # 🌟 อย่าลืม import memory_core ไว้ด้านบนสุดด้วยนะครับ
from contextlib import asynccontextmanager # 🌟 [เพิ่มบรรทัดนี้]

from system1_fast import think_fast
from system2_slow import think_slow

@asynccontextmanager
async def lifespan(app: FastAPI):
    # โค้ดส่วนนี้จะทำงานตอน "เปิด" Server (เราปล่อยว่างไว้ก่อน)
    yield
    
    # โค้ดส่วนนี้จะทำงานตอน "ปิด" Server (ตอนกด Ctrl+C)
    print("\n🛑 [API Server] ได้รับคำสั่งปิดระบบ... กำลังตัดการเชื่อมต่อ LLM!")
    memory_core.server_is_shutting_down = True

app = FastAPI(lifespan=lifespan)

HOST = "127.0.0.1"
PORT = 8000

# 🌟 เปลี่ยนจากตัวแปรตายตัว เป็นก้อน Dictionary (stats)
class AgentState(BaseModel):
    stats: Dict[str, float] 
    x: float
    y: float
    z: float
    objects_nearby: List[str]
    last_feedback: str = "" 

@app.post("/think")
async def think(state: AgentState):
    
    # ⚡ 1. ส่ง stats เหมาเข่งให้ System 1
    sys1_result = think_fast(
        stats=state.stats, 
        current_x=state.x,        
        current_z=state.z,        
        objects_nearby=state.objects_nearby, 
        last_feedback=state.last_feedback  
    )
    
    if sys1_result["action"] == "CALL_SYSTEM2":
        # 🧠 2. ส่ง stats เหมาเข่งให้ System 2
        sys2_result = think_slow(
            stats=state.stats, 
            current_x=state.x,        
            current_z=state.z,        
            objects_nearby=state.objects_nearby, 
            last_feedback=state.last_feedback,
            system1_thought=sys1_result["thought"] 
        )
        return sys2_result
        
    else:
        return sys1_result

if __name__ == "__main__":
    uvicorn.run("api_server:app", host=HOST, port=PORT, reload=False)

if __name__ == "__main__":
    uvicorn.run("api_server:app", host=HOST, port=PORT, reload=False)