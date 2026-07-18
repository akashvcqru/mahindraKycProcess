import base64
import io
import json
import logging
import os
import time
import requests

# Load .env to ensure we have AI_PROVIDER and API keys before validation scripts run
try:
    from dotenv import load_dotenv
    _cur_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_cur_dir)
    _env_path = os.path.join(_project_root, '.env')
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except Exception:
    pass

# Ensure OPENAI_API_KEY is not empty if provider is Claude or Gemini, to prevent early failures in validation scripts
_provider = os.getenv("AI_PROVIDER", "OpenAI")
if _provider in ("Claude", "Gemini") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "dummy-key-for-patched-request"

original_post = requests.post

def transform_openai_to_claude(openai_json):
    claude_messages = []
    messages = openai_json.get("messages", [])
    system_text = None
    
    for msg in messages:
        role = msg.get("role", "user")
        content_in = msg.get("content")
        
        if role == "system":
            if isinstance(content_in, str):
                system_text = (system_text + "\n" + content_in) if system_text else content_in
            elif isinstance(content_in, list):
                text_parts = [p.get("text", "") for p in content_in if p.get("type") == "text"]
                combined = " ".join(text_parts)
                system_text = (system_text + "\n" + combined) if system_text else combined
            continue
            
        claude_content = []
        if isinstance(content_in, list):
            for part in content_in:
                if part.get("type") == "text":
                    claude_content.append({
                        "type": "text",
                        "text": part.get("text")
                    })
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:image/"):
                        try:
                            header, base64_data = img_url.split(",", 1)
                            media_type = header.split(";")[0].replace("data:", "")
                        except Exception:
                            base64_data = img_url
                            media_type = "image/jpeg"
                    else:
                        base64_data = img_url
                        media_type = "image/jpeg"
                    
                    claude_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data
                        }
                    })
        elif isinstance(content_in, str):
            claude_content = content_in
            
        claude_messages.append({
            "role": role,
            "content": claude_content
        })
        
    claude_model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    claude_payload = {
        "model": claude_model,
        "max_tokens": openai_json.get("max_tokens", 4096),
        "messages": claude_messages
    }
    if system_text:
        claude_payload["system"] = system_text
        
    return claude_payload

def transform_claude_to_openai(claude_json):
    text_content = ""
    for part in claude_json.get("content", []):
        if part.get("type") == "text":
            text_content += part.get("text", "")
            
    # Extract JSON if present to conform with OpenAI strict JSON format expectations
    clean_content = text_content.strip()
    if '{' in clean_content or '[' in clean_content:
        start_brace = clean_content.find('{')
        start_bracket = clean_content.find('[')
        
        start = -1
        end = -1
        
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            start = start_brace
            end = clean_content.rfind('}')
        elif start_bracket != -1:
            start = start_bracket
            end = clean_content.rfind(']')
            
        if start != -1 and end != -1 and end > start:
            json_candidate = clean_content[start:end+1]
            try:
                json.loads(json_candidate)
                text_content = json_candidate
            except json.JSONDecodeError:
                pass
            
    openai_json = {
        "id": claude_json.get("id", "chatcmpl-mock"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": claude_json.get("model", "gpt-4o"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": claude_json.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": claude_json.get("usage", {}).get("output_tokens", 0),
            "total_tokens": claude_json.get("usage", {}).get("input_tokens", 0) + claude_json.get("usage", {}).get("output_tokens", 0)
        }
    }
    return openai_json

def transform_openai_to_gemini(openai_json):
    messages = openai_json.get("messages", [])
    system_text = None
    gemini_contents = []
    
    for msg in messages:
        role = msg.get("role", "user")
        if role == "assistant":
            role = "model"
        elif role == "system":
            content_in = msg.get("content")
            if isinstance(content_in, str):
                system_text = (system_text + "\n" + content_in) if system_text else content_in
            elif isinstance(content_in, list):
                text_parts = [p.get("text", "") for p in content_in if p.get("type") == "text"]
                combined = " ".join(text_parts)
                system_text = (system_text + "\n" + combined) if system_text else combined
            continue
            
        content_in = msg.get("content")
        gemini_parts = []
        
        if isinstance(content_in, list):
            for part in content_in:
                if part.get("type") == "text":
                    gemini_parts.append({
                        "text": part.get("text")
                    })
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:image/"):
                        try:
                            header, base64_data = img_url.split(",", 1)
                            media_type = header.split(";")[0].replace("data:", "")
                        except Exception:
                            base64_data = img_url
                            media_type = "image/png"
                    else:
                        base64_data = img_url
                        media_type = "image/png"
                    
                    gemini_parts.append({
                        "inlineData": {
                            "mimeType": media_type,
                            "data": base64_data
                        }
                    })
        elif isinstance(content_in, str):
            gemini_parts.append({
                "text": content_in
            })
            
        gemini_contents.append({
            "role": role,
            "parts": gemini_parts
        })
        
    gemini_payload = {
        "contents": gemini_contents
    }
    
    if system_text:
        gemini_payload["systemInstruction"] = {
            "parts": [
                {"text": system_text}
            ]
        }
        
    generation_config = {}
    if "temperature" in openai_json:
        generation_config["temperature"] = openai_json["temperature"]
    if "max_tokens" in openai_json:
        generation_config["maxOutputTokens"] = openai_json["max_tokens"]
        
    if generation_config:
        gemini_payload["generationConfig"] = generation_config
        
    return gemini_payload

def transform_gemini_to_openai(gemini_json):
    text_content = ""
    candidates = gemini_json.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            text_content += part.get("text", "")
            
    clean_content = text_content.strip()
    if '{' in clean_content or '[' in clean_content:
        start_brace = clean_content.find('{')
        start_bracket = clean_content.find('[')
        
        start = -1
        end = -1
        
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            start = start_brace
            end = clean_content.rfind('}')
        elif start_bracket != -1:
            start = start_bracket
            end = clean_content.rfind(']')
            
        if start != -1 and end != -1 and end > start:
            json_candidate = clean_content[start:end+1]
            try:
                json.loads(json_candidate)
                text_content = json_candidate
            except json.JSONDecodeError:
                pass
                
    usage = gemini_json.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", 0)
    completion_tokens = usage.get("candidatesTokenCount", 0)
    
    openai_json = {
        "id": "chatcmpl-mock-gemini",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gemini-flash-latest",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    }
    return openai_json

def custom_post(url, *args, **kwargs):
    if url == "https://api.openai.com/v1/chat/completions":
        provider = os.getenv("AI_PROVIDER", "OpenAI")
        if provider == "Python":
            resp = requests.Response()
            resp.status_code = 400
            resp.reason = "Bad Request"
            resp._content = json.dumps({
                "error": {
                    "message": "API call blocked: AI_PROVIDER is set to Python (LLM disabled)."
                }
            }).encode("utf-8")
            logging.warning("[custom_post] Blocked network API call because AI_PROVIDER is set to 'Python'.")
            return resp
            
        elif provider == "Claude":
            claude_key = os.getenv("CLAUDE_API_KEY", "")
            headers = {
                "x-api-key": claude_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            openai_payload = kwargs.get("json", {})
            claude_payload = transform_openai_to_claude(openai_payload)
            timeout = kwargs.get("timeout", 60)
            
            logging.info(f"Routing request to Claude API (Model: {claude_payload.get('model')})...")
            claude_resp = original_post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=claude_payload,
                timeout=timeout
            )
            
            resp = requests.Response()
            resp.status_code = claude_resp.status_code
            resp.headers = dict(claude_resp.headers)
            resp.reason = claude_resp.reason
            resp.url = claude_resp.url
            resp.request = claude_resp.request
            
            if claude_resp.status_code == 200:
                try:
                    claude_json = claude_resp.json()
                    openai_json = transform_claude_to_openai(claude_json)
                    resp._content = json.dumps(openai_json).encode("utf-8")
                except Exception as e:
                    logging.error(f"Error parsing Claude response: {e}")
                    resp._content = claude_resp.content
            else:
                logging.error(f"Claude API request failed ({claude_resp.status_code}): {claude_resp.text}")
                resp._content = claude_resp.content
                
            return resp

        elif provider == "Gemini":
            gemini_key = os.getenv("GEMINI_API_KEY", "")
            headers = {
                "content-type": "application/json",
                "X-goog-api-key": gemini_key
            }
            openai_payload = kwargs.get("json", {})
            gemini_payload = transform_openai_to_gemini(openai_payload)
            timeout = kwargs.get("timeout", 60)
            
            logging.info("Routing request to Gemini API (Model: gemini-flash-latest)...")
            gemini_resp = original_post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
                headers=headers,
                json=gemini_payload,
                timeout=timeout
            )
            
            resp = requests.Response()
            resp.status_code = gemini_resp.status_code
            resp.headers = dict(gemini_resp.headers)
            resp.reason = gemini_resp.reason
            resp.url = gemini_resp.url
            resp.request = gemini_resp.request
            
            if gemini_resp.status_code == 200:
                try:
                    gemini_json = gemini_resp.json()
                    openai_json = transform_gemini_to_openai(gemini_json)
                    resp._content = json.dumps(openai_json).encode("utf-8")
                except Exception as e:
                    logging.error(f"Error parsing Gemini response: {e}")
                    resp._content = gemini_resp.content
            else:
                logging.error(f"Gemini API request failed ({gemini_resp.status_code}): {gemini_resp.text}")
                resp._content = gemini_resp.content
                
            return resp
            
    return original_post(url, *args, **kwargs)

# Apply patch
requests.post = custom_post
logging.info("[AI Patch] requests.post successfully patched to route to Claude/Python if configured.")

# Patch easyocr.Reader to use bundled models folder if frozen
try:
    import easyocr
    original_reader = easyocr.Reader
    class PatchedReader(original_reader):
        def __init__(self, *args, **kwargs):
            import sys
            import os
            if getattr(sys, 'frozen', False):
                bundled_path = os.path.join(sys._MEIPASS, 'easyocr_models')
                if os.path.exists(bundled_path):
                    kwargs['model_storage_directory'] = bundled_path
            super().__init__(*args, **kwargs)
    easyocr.Reader = PatchedReader
    logging.info("[AI Patch] easyocr.Reader patched to use bundled models folder if frozen.")
except ImportError:
    pass

