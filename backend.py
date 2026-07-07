import os
import json
import asyncio
import traceback
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import jieba
import jieba.analyse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_sessions = {}

class TranscriptionSession:
    def __init__(self):
        self.text_segments = []
        self.start_time = datetime.now()
        self.last_activity_time = datetime.now()
        self.keywords = []
        self.highlights = []
        
    def add_segment(self, text):
        self.text_segments.append(text)
        self.last_activity_time = datetime.now()
        self.update_keywords()
        self.update_highlights()
        
    def get_duration(self):
        return int((datetime.now() - self.start_time).total_seconds())
    
    def get_word_count(self):
        return sum(len(segment) for segment in self.text_segments)
    
    def is_silent(self, threshold=5):
        elapsed = (datetime.now() - self.last_activity_time).total_seconds()
        return elapsed >= threshold
    
    def update_keywords(self):
        full_text = ' '.join(self.text_segments)
        print(f"Full text for keyword extraction: '{full_text}', length: {len(full_text)}")
        
        if len(full_text) < 5:
            self.keywords = []
            return
        
        try:
            keywords = jieba.analyse.extract_tags(full_text, topK=8, withWeight=False)
            self.keywords = keywords
            print(f"Extracted keywords: {keywords}")
        except Exception as e:
            print(f"Keyword extraction error: {e}")
            traceback.print_exc()
            self.keywords = []
    
    def update_highlights(self):
        full_text = ' '.join(self.text_segments)
        print(f"Full text for highlight extraction: '{full_text}'")
        self.highlights = []
        
        key_topics = ['创新', '创造', '研发', '技术', '产品', '市场', '用户', '需求', '解决方案', '问题',
                     '突破', '变革', '模式', '方法', '能力', '策略', '目标', '计划', '项目', '团队',
                     '投资', '融资', '合作', '竞争', '优势', '机会', '挑战', '风险', '趋势', '未来']
        
        sentences = full_text.split('。')
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
            
            for keyword in key_topics:
                if keyword in sentence:
                    self.highlights.append(sentence + '。')
                    break
        
        self.highlights = list(set(self.highlights))[:5]
        print(f"Extracted highlights: {self.highlights}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = id(websocket)
    active_sessions[session_id] = TranscriptionSession()
    print(f"Session {session_id} connected")
    
    try:
        while True:
            data = await websocket.receive()
            session = active_sessions[session_id]
            
            text = ""
            if data.get('text'):
                text = data['text'].strip()
            elif data.get('bytes'):
                try:
                    text = data['bytes'].decode('utf-8').strip()
                except:
                    text = ""
            
            print(f"Received raw data: {data}")
            
            if text:
                session.add_segment(text)
                print(f"Received text: '{text}', segments: {len(session.text_segments)}")
            
            await websocket.send_text(json.dumps({
                "type": "status",
                "duration": session.get_duration(),
                "word_count": session.get_word_count(),
                "keywords": session.keywords,
                "highlights": session.highlights,
                "is_silent": session.is_silent(),
                "segment_count": len(session.text_segments)
            }))
            
    except WebSocketDisconnect:
        print(f"Session {session_id} disconnected")
    except Exception as e:
        print(f"Error in session {session_id}: {e}")
        traceback.print_exc()
    finally:
        if session_id in active_sessions:
            del active_sessions[session_id]

@app.get("/health")
async def health():
    return {"status": "healthy"}

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/{full_path:path}")
async def serve_file(full_path: str):
    try:
        return FileResponse(full_path)
    except:
        return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)