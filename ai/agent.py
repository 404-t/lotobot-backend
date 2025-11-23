from openai import OpenAI
from lotobot.rag import RAGSystem
import os
import json
from dotenv import load_dotenv
from pathlib import Path


load_dotenv()

class Agent:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("API_KEY"),
        )
        with Path("lotobot/system_prompt.txt").open(encoding="utf-8") as f:
            self.system_prompt = f.read()
        with Path("lotobot/analysis_prompt.txt").open(encoding="utf-8") as f:
            self.analysis_prompt = f.read()
        with Path("lotobot/archive_analysis_prompt.txt").open(encoding="utf-8") as f:
            self.archive_analysis_prompt = f.read()
        with Path("lotobot/intent_prompt.txt").open(encoding="utf-8") as f:
            self.intent_prompt = f.read()
        with Path("lotobot/conversation_prompt.txt").open(encoding="utf-8") as f:
            self.conversation_prompt = f.read()
        
        self.rag = RAGSystem()
        self.rag.load_json("lotobot/lotteries.json")
    
    def _dict_to_string(self, obj):
        if isinstance(obj, dict):
            parts = []
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    parts.append(f"{key}: {self._dict_to_string(value)}")
                else:
                    parts.append(f"{key}: {value}")
            return ", ".join(parts)
        if isinstance(obj, list):
            return ", ".join(str(self._dict_to_string(item)) for item in obj)
        return str(obj)
    
    def extract_keywords(self, text, chat_context=None):
        messages = [{"role": "system", "content": self.system_prompt}]
        if chat_context:
            messages.extend(chat_context)
        messages.append({"role": "user", "content": text})
        
        response = self.client.chat.completions.create(
            model="x-ai/grok-4.1-fast:free",
            messages=messages
        )
        return response.choices[0].message.content
    
    def _detect_intent(self, user_query, chat_context=None):
        messages = [{"role": "system", "content": self.intent_prompt}]
        if chat_context:
            messages.extend(chat_context)
        messages.append({"role": "user", "content": user_query})
        
        response = self.client.chat.completions.create(
            model="x-ai/grok-4.1-fast:free",
            messages=messages
        )
        intent = response.choices[0].message.content.strip().lower()
        return "search" if "search" in intent else "answer"
    
    def process_query(self, user_query, chat_context=None):
        intent = self._detect_intent(user_query, chat_context)
        
        if intent == "search":
            keywords = self.extract_keywords(user_query, chat_context)
            rag_results = self.rag.search(keywords, top_k=3)
            
            lotteries_text = []
            for r in rag_results:
                lottery = r["data"]
                text = self._dict_to_string(lottery)
                lotteries_text.append(text)
            
            lotteries_data = "\n".join(lotteries_text)
            
            messages = [{"role": "system", "content": self.analysis_prompt}]
            if chat_context:
                messages.extend(chat_context)
            messages.append({"role": "user", "content": f"Лотереи:\n{lotteries_data}"})
            
            response = self.client.chat.completions.create(
                model="x-ai/grok-4.1-fast:free",
                messages=messages
            )
            content = response.choices[0].message.content
            
            try:
                parsed_content = json.loads(content)
                content = parsed_content
            except json.JSONDecodeError:
                pass
        else:
            messages = [{"role": "system", "content": self.conversation_prompt}]
            if chat_context:
                messages.extend(chat_context)
            messages.append({"role": "user", "content": user_query})
            
            response = self.client.chat.completions.create(
                model="x-ai/grok-4.1-fast:free",
                messages=messages
            )
            content = response.choices[0].message.content
        
        return json.dumps({"action": intent, "content": content}, ensure_ascii=False)
    
    def analyze_archive(self, archive_data):
        data_text = self._dict_to_string(archive_data) if isinstance(archive_data, (dict, list)) else str(archive_data)
        
        response = self.client.chat.completions.create(
            model="x-ai/grok-4.1-fast:free",
            messages=[
                {"role": "system", "content": self.archive_analysis_prompt},
                {"role": "user", "content": f"Архивные данные:\n{data_text}"}
            ]
        )
        return response.choices[0].message.content
