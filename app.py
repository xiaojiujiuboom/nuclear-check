import streamlit as st
import requests
import json
import re
import time
import ast # 新增：用于处理类 Python 字典格式
import datetime # 新增：用于记录收藏时间
import os  # 新增：用于文件持久化操作

# --- 1. 页面配置 (必须在最前面) ---
st.set_page_config(
    page_title="Nuclear Knowledge Hub", 
    layout="wide", 
    page_icon="⚛️",
    initial_sidebar_state="expanded"
)

# --- 0. 持久化存储模块 (新增) ---
FAV_FILE = "favorites.json"

def get_fav_file_path():
    """根据当前用户ID生成文件名，实现多用户隔离"""
    user_id = st.session_state.get("user_id", "default").strip()
    if not user_id: user_id = "default"
    # 过滤非法字符，防止文件名错误
    safe_id = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', user_id)
    return f"favorites_{safe_id}.json"

def load_favorites():
    """从当前用户的本地文件加载收藏"""
    file_path = get_fav_file_path()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_favorites():
    """保存收藏到当前用户的本地文件"""
    file_path = get_fav_file_path()
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(st.session_state["favorites"], f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"保存失败: {e}")

# --- 初始化 Session State ---
if "user_id" not in st.session_state:
    st.session_state["user_id"] = "default"

if "favorites" not in st.session_state:
    st.session_state["favorites"] = load_favorites()

# 结果缓存 (防止刷新丢失当前页面内容)
if "check_result" not in st.session_state:
    st.session_state["check_result"] = None
if "search_result" not in st.session_state:
    st.session_state["search_result"] = None
if "rewrite_result" not in st.session_state:
    st.session_state["rewrite_result"] = None

# --- 2. 获取 API Key (双重保险模式) ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    else:
        API_KEY = ""
except FileNotFoundError:
    API_KEY = ""

if not API_KEY:
    with st.sidebar:
        st.divider()
        st.warning("🔒 未检测到配置文件的 API Key")
        API_KEY = st.text_input("请在此临时粘贴 API Key:", type="password", help="建议在 Streamlit Secrets 中配置 GEMINI_API_KEY 以免去每次输入的麻烦。")

def get_secret_with_default(key, default):
    """兼容本地/云端环境读取 secrets。"""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

GEMINI_BASE_URL = get_secret_with_default("GEMINI_BASE_URL", "https://api.xiaotiangong.com").rstrip("/")
GEMINI_API_VERSION = get_secret_with_default("GEMINI_API_VERSION", "v1beta").strip("/")
GEMINI_MODEL = get_secret_with_default("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL = get_secret_with_default("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

# --- 3. CSS 样式优化 ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* 核心卡片容器 */
        .card-container {
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.2rem;
            transition: transform 0.2s;
            position: relative;
        }
        .card-container:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        
        /* 智能核查卡片 */
        .check-card {
            background-color: #262730;
            border: 1px solid #464b59;
            color: #FAFAFA;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        
        /* 学术检索卡片 */
        .research-card {
            background-color: #2d3748;
            border: 1px solid #4a5568;
            border-left: 5px solid #63b3ed;
            color: #e2e8f0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        
        /* 学术综述卡片 */
        .overview-card {
            background-color: #322659;
            border: 1px solid #5a4b81;
            border-left: 5px solid #9f7aea;
            color: #e9d8fd;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }

        /* 学术改写卡片 */
        .rewrite-card {
            background-color: #234e52;
            border: 1px solid #285e61;
            border-left: 5px solid #38b2ac;
            color: #e6fffa;
            font-family: "Noto Serif SC", serif;
            line-height: 1.8;
            font-size: 1.05rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        
        /* 翻译部分样式 - 已修改为白色 #ffffff */
        .translation-section {
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px dashed #4fd1c5;
            color: #ffffff; 
            font-size: 0.95rem;
            font-style: italic;
        }

        /* 链接按钮样式 */
        .source-link {
            display: inline-block;
            background-color: #363945;
            color: #e0e0e0 !important;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            text-decoration: none;
            margin-right: 8px;
            margin-bottom: 6px;
            border: 1px solid #555;
            transition: all 0.2s;
        }
        .source-link:hover {
            background-color: #4a4d5a;
            color: #ff4b4b !important;
            border-color: #ff4b4b;
        }
        
        .scihub-btn {
            background-color: #2c0b0e;
            color: #fc8181 !important;
            border: 1px solid #822727;
        }
        .scihub-btn:hover {
            background-color: #451014;
            color: #feb2b2 !important;
            border-color: #fc8181;
        }

        /* 证据容器样式 */
        .evidence-container {
            background-color: #f8f9fa; 
            border-radius: 6px;
            padding: 15px;
            margin-top: 12px;
            border: 1px solid #e9ecef;
        }

        .quote-item {
            border-left: 3px solid #63b3ed;
            padding-left: 10px;
            margin-bottom: 8px;
            color: #1f2937; 
            font-size: 0.95em;
            font-family: "Noto Serif SC", serif;
            line-height: 1.5;
        }
        
        .tag-pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            margin-right: 5px;
            background-color: #e2e8f0; 
            color: #2d3748; 
            border: 1px solid #cbd5e0;
        }
        
        /* 用户ID输入框美化 */
        .user-input {
            border-bottom: 2px solid #4fd1c5;
        }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心函数：固定模型配置 ---
def get_prioritized_models(api_key):
    """
    新配置：优先 Gemini 3 Flash Preview，失败时自动切到 2.5 Flash。
    """
    if not api_key:
        return [], "API Key 未配置"
    model_list = [GEMINI_MODEL, GEMINI_FALLBACK_MODEL]
    # 去重并过滤空值
    model_list = [m for i, m in enumerate(model_list) if m and m not in model_list[:i]]
    return model_list, "Success"

# --- 5. 增强版 API 调用：兼容新网关地址 ---
def smart_api_call(model_list, payload, api_key, status_box=None):
    """
    智能调用函数：自动重试模型节点，处理 429/400 错误
    """
    last_error = None
    
    for i, model_name in enumerate(model_list):
        if not model_name.startswith("models/"): 
            full_model_name = f"models/{model_name}"
        else:
            full_model_name = model_name
            
        api_url = f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/{full_model_name}:generateContent?key={api_key}"
        
        if status_box:
            status_box.write(f"🔄 正在尝试模型节点 ({i+1}/{len(model_list)}): `{model_name.replace('models/', '')}` ...")
        
        try:
            response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
            
            if response.status_code == 200:
                return response
            
            elif response.status_code == 400:
                if "tools" in payload:
                    if status_box: status_box.write("⚠️ 检测到工具兼容性问题，正在切换至纯文本分析模式...")
                    payload_no_tools = payload.copy()
                    del payload_no_tools["tools"]
                    response_retry = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload_no_tools)
                    if response_retry.status_code == 200:
                        return response_retry
                last_error = response
                continue

            elif response.status_code in [429, 503, 500]:
                if status_box: status_box.write(f"⏳ 模型 `{model_name}` 繁忙或配额耗尽，自动切换下一节点...")
                time.sleep(1)
                last_error = response
                continue
            
            else:
                last_error = response
                continue

        except Exception as e:
            if status_box: status_box.write(f"❌ 网络异常: {e}")
            continue

    return last_error

# --- 6. 辅助函数：安全提取与解析 ---
def get_response_text(response):
    """安全提取响应文本，避免 IndexError"""
    if not response: return None
    try:
        data = response.json()
        if 'candidates' in data and data['candidates']:
            parts = data['candidates'][0].get('content', {}).get('parts', [])
            if parts:
                return parts[0].get('text', '')
        return None
    except Exception as e:
        return None

def get_response_error(response):
    """提取接口错误详情，便于定位问题。"""
    if not response:
        return "无响应"
    try:
        data = response.json()
        if isinstance(data, dict):
            if isinstance(data.get("error"), dict):
                err = data.get("error", {})
                msg = err.get("message") or json.dumps(err, ensure_ascii=False)
                return f"HTTP {response.status_code}: {msg}"
            if data.get("msg"):
                return f"HTTP {response.status_code}: {data.get('msg')}"
            return f"HTTP {response.status_code}: {json.dumps(data, ensure_ascii=False)[:400]}"
    except Exception:
        pass
    text = getattr(response, "text", "")
    text = text[:400] if text else "未知错误"
    return f"HTTP {getattr(response, 'status_code', 'N/A')}: {text}"

def extract_grounding_sources(response):
    """
    从 Gemini grounded response 中提取可点击来源。
    """
    if not response:
        return []
    try:
        data = response.json()
    except Exception:
        return []

    sources = []
    seen = set()
    candidates = data.get("candidates", [])
    for cand in candidates:
        meta = cand.get("groundingMetadata", {})
        chunks = meta.get("groundingChunks", [])
        for ch in chunks:
            web_info = ch.get("web", {})
            uri = web_info.get("uri", "").strip()
            title = web_info.get("title", "").strip() or "来源"
            if uri and uri not in seen:
                seen.add(uri)
                sources.append({"title": title, "url": uri})
    return sources

def parse_json_response(text):
    if not text: return None
    try:
        return json.loads(text)
    except:
        pass
    
    try:
        clean_text = re.sub(r'```json\s*', '', text)
        clean_text = re.sub(r'```\s*$', '', clean_text)
        clean_text = clean_text.strip()
        return json.loads(clean_text)
    except:
        pass

    try:
        start_obj = text.find('{')
        start_list = text.find('[')
        
        if start_obj == -1 and start_list == -1:
            return None
            
        if start_obj != -1 and (start_list == -1 or start_obj < start_list):
            start = start_obj
            end_char = '}'
        else:
            start = start_list
            end_char = ']'
            
        end = text.rfind(end_char)
        if end != -1 and end > start:
            json_str = text[start : end+1]
            return json.loads(json_str)
    except:
        pass

    try:
        if start_obj != -1 and end != -1:
             potential_dict = text[start : end+1]
             return ast.literal_eval(potential_dict)
    except:
        pass

    return None

# --- 新增：收藏功能函数 (颗粒度+持久化) ---
def add_to_favorites(category, title, content_data):
    """
    category: 'Check' (单条结论) | 'Search' (单篇文献/综述) | 'Rewrite' (改写结果)
    title: 简短标题
    content_data: 完整数据 (JSON或文本)
    """
    # 1. 查重
    for item in st.session_state["favorites"]:
        if item['category'] == category and item['content'] == content_data:
            st.toast("⚠️ 该内容已在收藏夹中", icon="👀")
            return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = {
        "id": f"{category}_{int(time.time()*1000)}",
        "category": category,
        "title": title[:50] + "..." if len(title) > 50 else title, # 限制标题长度
        "content": content_data,
        "time": timestamp
    }
    
    # 2. 添加到 Session
    st.session_state["favorites"].append(item)
    
    # 3. 保存到本地文件 (持久化)
    save_favorites()
    
    st.toast(f"✅ 已收藏: {title[:15]}...", icon="⭐")

def delete_favorite(item_id):
    # 根据 ID 删除
    st.session_state["favorites"] = [item for item in st.session_state["favorites"] if item['id'] != item_id]
    save_favorites()
    st.rerun()

# --- 7. 核心页面逻辑 ---
# 侧边栏
with st.sidebar:
    st.title("⚛️ Nuclear Hub")
    st.info("**Pro Max v6.3 (Stable)**\n\n修复了结果解析可能导致的崩溃问题。")
    
    # --- 用户 ID 管理 & 备份 ---
    st.markdown("### 👤 档案管理")
    
    # 显示当前 ID
    user_id_input = st.text_input("当前用户 ID (回车切换)", value=st.session_state["user_id"], help="不同的ID将保存不同的收藏记录")
    
    if user_id_input != st.session_state["user_id"]:
        st.session_state["user_id"] = user_id_input
        st.session_state["favorites"] = load_favorites() # 切换用户时重新加载数据
        st.rerun()
    
    st.caption(f"当前数据文件: `{get_fav_file_path()}`")
    st.divider()

    if not API_KEY:
        st.warning("🔒 未检测到 API Key")
        API_KEY = st.text_input("请在此临时粘贴 API Key:", type="password", help="建议在 Streamlit Secrets 中配置")
    
    st.caption("Powered by Google Gemini & Streamlit")

st.title("Nuclear Knowledge Hub")
st.caption("🚀 核科学事实核查、学术检索与专业改写平台")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 智能核查", "🔬 学术检索", "✍️ 学术改写", "⭐ 我的收藏"])

# ==========================================
# 模块一：智能核查 (Nuclear Check)
# ==========================================
with tab1:
    col1_check, col2_check = st.columns([1, 1], gap="large")

    with col1_check:
        st.markdown("#### 📝 输入待核查内容")
        user_text_check = st.text_area("待核查文本", height=400, label_visibility="collapsed", placeholder="在此粘贴待核实信息...\n例如：中国现在有58座核电站？", key="input_check")
        check_btn = st.button("🚀 开始深度核查", type="primary", use_container_width=True, key="btn_check")

    with col2_check:
        st.markdown("#### 📊 核查报告")
        
        # 1. 触发逻辑
        if check_btn and user_text_check:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key")
            else:
                status_box = st.status("正在启动多模型引擎...", expanded=True)
                model_list, msg = get_prioritized_models(API_KEY)
                
                if not model_list:
                    status_box.update(label="初始化失败", state="error")
                    st.error(f"无法获取模型列表: {msg}")
                else:
                    # --- 完整 Prompt (未修改) ---
                    prompt_check = f"""
                    你是一个严谨的核聚变与等离子体物理专家，同时拥有实时联网核查的能力。
                    请利用 Google Search 工具，核查以下文本中的每一个事实陈述。

                    **用户输入文本：**
                    '''{user_text_check}'''

                    **重要指示：**
                    1. **多源数据对比**：如果不同权威机构的数据不一致（例如 IAEA 数据 vs 中国核能行业协会数据），**请不要只给出一个数字**，而必须将各方数据分别列出。
                    2. **原文引用 (双语 + 可定位)**：
                       - 对于每一个数据点，必须给出可在来源页面中检索到的**原文短句**。
                       - 如果引用原文是英文，后面必须附中文翻译。
                       - 额外提供 `search_hint`：可直接用于页面内查找的一段英文关键词（建议 6-16 个词）。
                    3. **实时性**：以搜索到的最新官方报告为准。
                    4. **来源准确性**：`url` 必须是直接包含该信息的页面链接，不要只给网站首页。

                    **输出格式要求（非常重要）：**
                    **严禁输出任何开场白或结束语（如"好的"、"以下是结果"）。**
                    **严禁在 JSON 内部使用未转义的换行符。**
                    **仅输出**以下 JSON 列表格式：
                    [
                        {{
                            "claim": "原文中的陈述",
                            "status": "正确/错误/存疑/数据不一致",
                            "correction": "综合分析。如果数据冲突，请在此说明差异原因。",
                            "evidence_list": [
                                {{
                                    "source_name": "机构名称",
                                    "content": "具体描述/数据 (如果是英文请附带中文翻译)",
                                    "search_hint": "可在页面内搜索定位的关键词短句",
                                    "url": "来源链接"
                                }}
                            ]
                        }}
                    ]
                    """
                    
                    payload = {"contents": [{"parts": [{ "text": prompt_check }]}], "tools": [{"google_search": {}}]}
                    response = smart_api_call(model_list, payload, API_KEY, status_box)
                    
                    # 使用新的安全提取函数
                    raw_content = get_response_text(response)

                    if raw_content:
                        check_results = parse_json_response(raw_content)
                        grounded_sources = extract_grounding_sources(response)
                        status_box.update(label="分析完成", state="complete", expanded=False)
                        st.session_state["check_result"] = {"data": check_results, "raw": raw_content, "grounded_sources": grounded_sources}
                    else:
                        status_box.update(label="请求失败", state="error")
                        st.error(f"请求失败或模型未返回内容：{get_response_error(response)}")

        # 2. 显示逻辑
        if st.session_state.get("check_result"):
            res_data = st.session_state["check_result"].get("data")
            raw_text = st.session_state["check_result"].get("raw")
            grounded_sources = st.session_state["check_result"].get("grounded_sources", [])

            if grounded_sources:
                st.markdown("##### 🔗 可追溯来源 (Grounding)")
                st.caption("以下链接来自模型工具返回的原始可追溯来源，可优先用于核对。")
                for src in grounded_sources[:8]:
                    st.markdown(f"- [{src.get('title', '来源')}]({src.get('url', '#')})")
            
            if res_data and isinstance(res_data, list):
                for idx, item in enumerate(res_data):
                    status = item.get('status', '存疑')
                    # 颜色逻辑
                    if "错" in status:
                        border_color = "#ff4b4b"; icon = "❌"; title_color = "#ff8a80"
                    elif "疑" in status or "不一致" in status:
                        border_color = "#ffa726"; icon = "⚠️"; title_color = "#ffcc80"
                    else:
                        border_color = "#66bb6a"; icon = "✅"; title_color = "#a5d6a7"
                    
                    with st.container():
                        # --- 卡片渲染 ---
                        st.markdown(f"""
                        <div class="card-container check-card" style="border-left: 5px solid {border_color};">
                            <div style="margin-bottom: 12px;">
                                <span style="font-weight: bold; font-size: 1.3em; color: {title_color};">{icon} {status}</span>
                                <div style="color: #b0bec5; font-size: 0.9em; margin-top: 4px;">陈述：{item.get('claim', '')}</div>
                            </div>
                            <div style="margin-bottom: 15px; line-height: 1.6;">
                                <b>💡 专家分析：</b><br>{item.get('correction', '无详细分析')}
                            </div>
                        """, unsafe_allow_html=True)
                        
                        evidence_list = item.get('evidence_list', [])
                        if not evidence_list and 'evidence_quote' in item: 
                            evidence_list = [{'source_name': '权威数据', 'content': item['evidence_quote'], 'url': '#'}]
                        
                        if evidence_list:
                            st.markdown('<div class="evidence-container">', unsafe_allow_html=True)
                            st.markdown('<div style="color: #555; margin-bottom: 8px; font-weight:bold;">🔍 权威数据/原文证据：</div>', unsafe_allow_html=True)
                            for ev in evidence_list:
                                st.markdown(f"""
                                <div class="quote-item">
                                    <span class="tag-pill">[{ev.get('source_name', '来源')}]</span>
                                    "{ev.get('content', '')}"<br>
                                    {'<span style="color:#5f6368; font-size:0.88em;">🔎 页面检索建议: ' + ev.get('search_hint', '') + '</span><br>' if ev.get('search_hint') else ''}
                                    <a href="{ev.get('url', '#')}" target="_blank" class="source-link" style="margin-top:4px; display:inline-block;">🔗 来源</a>
                                </div>
                                """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                        # --- 独立收藏按钮 ---
                        col_space, col_fav = st.columns([6, 1])
                        with col_fav:
                            if st.button("⭐ 收藏", key=f"fav_chk_{idx}", help="收藏这条核查结论"):
                                add_to_favorites("核查结论", item.get('claim'), item)
            else:
                st.warning("原始结果展示：")
                st.markdown(raw_text)

# ==========================================
# 模块二：学术检索 (Nuclear Search)
# ==========================================
with tab2:
    col1_search, col2_search = st.columns([1, 1], gap="large")
    
    with col1_search:
        st.markdown("#### 🔍 学术搜索引擎")
        search_query = st.text_input("请输入研究课题、关键词或问题", label_visibility="collapsed", placeholder="例如：可控核聚变 2024年 突破性进展 Q值", key="input_search")
        search_btn = st.button("🔬 开始学术检索", type="primary", use_container_width=True, key="btn_search")

    with col2_search:
        st.markdown("#### 📚 检索结果")
        
        if search_btn and search_query:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key")
            else:
                status_box_search = st.status("正在进行深度学术检索...", expanded=True)
                model_list, _ = get_prioritized_models(API_KEY)
                
                if model_list:
                    # --- 恢复完整的 Prompt (未修改) ---
                    prompt_search = f"""
                    你是一位资深的核科学研究员。请利用 Google Search 为用户寻找**真实存在**的权威学术文献、官方技术报告、行业白皮书或权威数据库记录。

                    **用户课题：** "{search_query}"

                    **任务 (两部分)：**
                    1. **Overview (综述)**: 基于搜索到的所有文献或数据库或相关官方报道，用中文写一段 150 字左右的学术综述，总结该领域的最新进展或回答用户问题。
                    2. **Papers (文献列表)**: 列出具体的文献、报告或数据库条目。

                    **严厉禁止 (Anti-Hallucination)：**
                    1. 严禁编造标题、作者、发布机构、报告编号、期刊或链接。
                    2. 严格区分“新闻报道”与“原始报告/论文”，优先引用原始出处
                    3. 如果没有 PDF 链接、DOI 或官方归档页面，请留空。
                    4. 每条 papers 必须给出可在页面中检索的 `search_hint`（英文关键词短句，6-16词）。

                    **执行步骤：**
                    1. 搜索 Nature, Science等期刊, IAEA (国际原子能机构), OECD-NEA (核能署), ITER, DOE (美国能源部), WNA (世界核协会) 等官方渠道等来源。
                    2. 提取关键数据，确保来源链接真实有效且可访问。
                    3. 编写综述，按学术规范整理输出。

                    **输出格式要求（非常重要）：**
                    **严禁输出任何开场白（如"好的"、"我找到了"等）。**
                    **仅输出**纯 JSON 对象，格式如下：
                    {{
                        "overview": "这里写中文综述，总结研究现状...",
                        "papers": [
                            {{
                                "title": "标题 (必须完全匹配搜索结果，如果是英文，请在括号内附上中文翻译)",
                                "authors": "作者/机构",
                                "publication": "来源 (如 Nature, IAEA)",
                                "year": "年份",
                                "summary": "详细摘要 (请保留英文原文，并在后面附带中文翻译)",
                                "search_hint": "可在页面内检索定位的关键词短句",
                                "doi": "DOI或空字符串",
                                "url": "真实URL"
                            }}
                        ]
                    }}
                    """
                    
                    payload = {"contents": [{"parts": [{ "text": prompt_search }]}], "tools": [{"google_search": {}}]}
                    response = smart_api_call(model_list, payload, API_KEY, status_box_search)
                    
                    # 使用新的安全提取函数
                    raw_content = get_response_text(response)

                    if raw_content:
                        search_results = parse_json_response(raw_content)
                        grounded_sources = extract_grounding_sources(response)
                        status_box_search.update(label="检索完成", state="complete", expanded=False)
                        st.session_state["search_result"] = {"data": search_results, "raw": raw_content, "grounded_sources": grounded_sources}
                    else:
                        status_box_search.update(label="请求失败", state="error")
                        st.error(f"请求失败或模型未返回内容：{get_response_error(response)}")
        
        # 2. 显示逻辑
        if st.session_state.get("search_result"):
            s_res = st.session_state["search_result"].get("data")
            s_raw = st.session_state["search_result"].get("raw")
            grounded_sources = st.session_state["search_result"].get("grounded_sources", [])
            
            if s_res and isinstance(s_res, dict):
                papers = s_res.get('papers', [])
                overview = s_res.get('overview', "")
                
                # --- 综述部分 ---
                if overview:
                    with st.container():
                        st.markdown(f"""
                        <div class="card-container overview-card">
                            <div style="font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">🧪 学术综述 (Overview)</div>
                            <div style="line-height: 1.6; font-size: 1.0em;">{overview}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        # 综述的收藏按钮
                        col_sp, col_fv = st.columns([6, 1])
                        with col_fv:
                            if st.button("⭐ 收藏综述", key="fav_overview"):
                                add_to_favorites("学术综述", f"关于 {search_query} 的综述", overview)
                    
                    st.divider()

                # --- 文献列表部分 ---
                if papers:
                    st.success(f"检索到 {len(papers)} 篇相关文献")
                    if grounded_sources:
                        st.caption("以下为模型工具返回的可追溯来源链接，可优先核对：")
                        for src in grounded_sources[:8]:
                            st.markdown(f"- [{src.get('title', '来源')}]({src.get('url', '#')})")
                    for idx, item in enumerate(papers):
                        with st.container():
                            # 卡片
                            st.markdown(f"""
                            <div class="card-container research-card">
                                <div style="font-size: 1.2em; font-weight: bold; color: #63b3ed; margin-bottom: 5px;">📄 {item.get('title', '无标题')}</div>
                                <div style="font-size: 0.9em; color: #a0aec0; margin-bottom: 15px;">
                                    {item.get('authors', 'N/A')} | {item.get('publication', 'N/A')}, {item.get('year', 'N/A')}
                                </div>
                                <div style="border-top: 1px solid #4a5568; margin-bottom: 10px;"></div>
                                <div style="line-height: 1.6; color: #cbd5e0; font-family: 'Noto Serif SC', serif;">
                                    {item.get('summary', '暂无摘要')}
                                </div>
                                {"<div style='margin-top:8px; font-size:0.88em; color:#9fb3c8;'>🔎 页面检索建议: " + item.get('search_hint', '') + "</div>" if item.get('search_hint') else ""}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # 操作栏：链接 + 收藏
                            col_l, col_f = st.columns([5, 1])
                            with col_l:
                                links_html = f'<a href="{item.get("url", "#")}" target="_blank" class="source-link">🔗 原文</a>'
                                if item.get('doi'):
                                    links_html += f' <a href="https://x.sci-hub.org.cn/{item.get("doi")}" target="_blank" class="source-link scihub-btn">🔓 Sci-Hub</a>'
                                st.markdown(links_html, unsafe_allow_html=True)
                            
                            with col_f:
                                if st.button("⭐ 收藏", key=f"fav_paper_{idx}", help="收藏这篇文献"):
                                    add_to_favorites("学术文献", item.get('title'), item)
            else:
                st.markdown(s_raw)

# ==========================================
# 模块三：学术改写 (Academic Rewrite)
# ==========================================
with tab3:
    col1_rewrite, col2_rewrite = st.columns([1, 1], gap="large")

    with col1_rewrite:
        st.markdown("#### ✍️ 原始草稿")
        user_text_rewrite = st.text_area("待改写文本", height=500, label_visibility="collapsed", placeholder="请在此粘贴...", key="input_rewrite")
        rewrite_btn = st.button("✨ 开始学术改写", type="primary", use_container_width=True, key="btn_rewrite")

    with col2_rewrite:
        st.markdown("#### 🖋️ 改写结果")
        
        if rewrite_btn and user_text_rewrite:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key")
            else:
                status_box_rewrite = st.status("正在进行语言润色...", expanded=True)
                model_list, _ = get_prioritized_models(API_KEY)
                
                if model_list:
                    # --- 恢复完整的 Prompt (未修改) ---
                    prompt_rewrite = f"""
                    你是一位在高级核杂质期刊有丰富经验的**人类学术编辑**。
                    请对以下文本进行**彻底的去AI化（De-AI）改写**，并提供双语对照。【需要注意的是我提供给你的句子有可能有些部分或是词语是可以采纳的，你不必每个词都完全转换。只需要符合学术要求即可】

                    **待改写文本：**
                    '''{user_text_rewrite}'''

                    **🚫 负面约束（绝对禁止 - Violations will be rejected）：**
                    1.  **禁止滥用连接副词**：严禁在句中堆砌你认为高大上的 "Fundamentally", "Crucially", "Furthermore", "Moreover", "Additionally", "Importantly"等副词进行强调。请通过句子内在的逻辑流来衔接，而非生硬的路标词。
                    2.  **拒绝名词化（Nominalization）**：例如：不要说 "The realization of X necessitates Y"（X的实现需要Y），要说 "To realize X, we must Y"（为了实现X，我们必须Y）。少用抽象名词（如 modality, provision, utilization, facilitation）。
                    3.  **拒绝僵硬的长难句**：不要写那种中间没有停顿、修饰语密集堆砌的长句。句子要有呼吸感（Rhythm），自然地长短句结合。
                    4.  **去"机器味"**：像人类专家一样直接表达观点。

                    **✅ 核心目标：**
                    1.  **人类化（Human-like）**：模仿人类专家的写作习惯，词汇选择要精准但不做作。
                    2.  **双语输出（Bilingual Output）**：
                        -   如果改写后的正文是**英文**，必须在下方附上高水平的**中文翻译**。
                        -   如果改写后的正文是**中文**，必须在下方附上地道的**英文翻译**。
                        -   翻译也要符合上述的学术标准，不要直译。

                    **✅可以参考学习模仿以下PPCF\PR系列的文章的写作风格：**
                      1.  "The cutoff energy and the divergence of the protons generated by the target normal sheath
acceleration mechanism are known to be significantly influenced by micrometer and
nanometer-size structures on the target front and rear surfaces. Specifically, the cutoff energy is
significantly enhanced by creating a central rectangular groove (RG) on the target front surface,
as shown in a recent study (Khan and Saxena 2023 Phys. Plasmas 30 063102). Here, we report
on 2D particle-in-cell simulations to thoroughly explore the effect of the depth of the central RG
on the energy spectra of the accelerated protons. The proton cutoff energy is found to enhance
drastically as a result of relativistically induced transparency as the thickness of the rear wall of
the groove is reduced from a few micrometers to a few tens of nanometers, however, it drops
sharply as the thickness of the rear wall is further reduced towards creating a complete hole
through the target." 
                      2.  "The interaction of a high-intensity femtosecond laser pulse
with a solid target results in highly energetic ions with MeV
energies. These ion sources are of much interest as they offer
measurement of fast-evolving electric and magnetic fields
using proton radiography technique. Other potential
cutting-edge applications, in the foresight, include hadron
therapy, isochoric heating of matter, fast ignition of
fusion targets, and many more."
                      3.  "In the present work, we investigate the impact of the depth
of a micrometer-size groove on the front side of the target, or
in other words the role of the thickness of the rear wall of the
grooved target, in improving proton cutoff energies and their
angular divergence. In particular, we investigate the variation
in proton energy spectra as the thickness of the rear wall of the
groove is reduced from a few micrometers to a couple of tens
of nanometers, and then to the case of no wall representing a
target with a complete hole through it. It is observed that the
onset time of relativistically induced transparency of the target
rear wall with respect to the peak of the laser pulse plays a key
role in determining the optimum width/thickness of the target
rear wall. This is in agreement with the previous studies" 
                    4. “Proton generation, transport and interaction with hollow cone targets are investigated by means of two-dimensional PIC simulations. A
scaled-down hollow cone with gold walls, a carbon tip and a curved hydrogen foil inside the cone has been considered. Proton acceleration is
driven by a 1020 W$cm	2 and 1 ps laser pulse focused on the hydrogen foil. Simulations show an important surface current at the cone walls
which generates a magnetic field. This magnetic field is dragged by the quasi-neutral plasma formed by fast protons and co-moving electrons
when they propagate towards the cone tip. As a result, a tens of kT Bz field is set up at the cone tip, which is strong enough to deflect the protons
and increase the beam divergence substantially. We propose using heavy materials at the cone tip and increasing the laser intensity in order to
mitigate magnetic field generation and proton beam divergence.”
                 5.“The standard proton fast ignition scheme assumes that the
proton beam is generated inside a hollow cone attached to an
inertial fusion capsule by means of the TNSA scheme.Most
of the proton FI calculations carried out so far are based on the
strong assumptions of ideal perfectly collimated beams and
optimal target configurations, which clearly under-estimate the
laser energy requirements for ignition. Other studies assumed that proton acceleration and transport within the cone
takes place in an idealmanner, i.e. protons are focused on the cone
tip and emerge with a given divergence angle. In addition, it is
widely assumed that there are not any relevant interactions be-
tween the proton beam and the cone tip. Only recently, collective
stopping of ion beams in solid matter has been reported”
                 6.“This article is organised as follows. In Section 2, the data
used in PIC simulations are described. Section 3 summarises
the results obtained for the proton beam generation and
transport within a standard cone design. Next, in Section 4,it
is proposed using heavy elements in the cone tip and higher
intensity laser pulses in order to mitigate the magnetic field
growth and the subsequent beam deflection at the cone tip.
Finally, conclusions and future work are summarized in Sec-
tion 5.”
                7.“Alarge number ofstudies have been performed to understand the mechanism involved in the laser-plasma
interaction-driven proton/ion acceleration. Among all possible candidates the target normal sheath
acceleration (TNSA) mechanism [9–11] has received wider attention than other (radiation pressure-based)
mechanisms. The paramount factor has been the wide accessibility ofthe laser parameters required for the
TNSAmechanism to operate. In this mechanism, the energetic electrons generated bylaser-plasma interaction
at the front surface ofthe target escape to the rear side ofthe target. This electron cloud while emerging from the
rear surface ofthe target forms a strong sheath electric field which is responsible for accelerating protons/ions to
several 10s ofMeV energies.”


                    **输出格式（必须严格遵守）：**
                    请按以下标签分隔内容：

                    [REWRITE]
                    (这里是改写后的优美学术文本)

                    [TRANSLATION]
                    (这里是对应的另一种语言的高水平翻译)
                    """
                    
                    payload = {"contents": [{"parts": [{ "text": prompt_rewrite }]}]}
                    response = smart_api_call(model_list, payload, API_KEY, status_box_rewrite)
                    
                    # 使用新的安全提取函数
                    raw_content = get_response_text(response)

                    if raw_content:
                        status_box_rewrite.update(label="润色完成", state="complete", expanded=False)
                        
                        rewrite_c = raw_content
                        trans_c = ""
                        if "[REWRITE]" in raw_content and "[TRANSLATION]" in raw_content:
                            parts = raw_content.split("[TRANSLATION]")
                            rewrite_c = parts[0].replace("[REWRITE]", "").strip()
                            trans_c = parts[1].strip()
                        
                        st.session_state["rewrite_result"] = {
                            "rewrite": rewrite_c, 
                            "translation": trans_c, 
                            "draft": user_text_rewrite
                        }
                    else:
                        status_box_rewrite.update(label="请求失败", state="error")
                        st.error(f"请求失败或模型未返回内容：{get_response_error(response)}")

        if st.session_state.get("rewrite_result"):
            res = st.session_state["rewrite_result"]
            
            # --- 改写结果展示 + 收藏 ---
            st.markdown(f"""
            <div class="card-container rewrite-card">
                <div style="margin-bottom: 10px; font-weight: bold; color: #81e6d9;">🖋️ Revised Text:</div>
                {res['rewrite'].replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([6, 1])
            with c2:
                if st.button("⭐ 收藏改写", key="fav_btn_rewrite"):
                    title_preview = res["rewrite"][:30].replace("\n", " ") + "..."
                    add_to_favorites("改写结果", title_preview, res)
            
            # --- 翻译展示 ---
            if res.get('translation'):
                st.markdown(f"""
                <div class="translation-section">
                    <div style="margin-bottom: 8px; font-weight: bold;">🌐 Translation:</div>
                    {res['translation'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

# ==========================================
# 模块四：我的收藏 (Favorites)
# ==========================================
with tab4:
    st.markdown(f"### ⭐ {st.session_state['user_id']} 的知识库")
    
    # --- 新增：数据备份与恢复区域 ---
    with st.expander("☁️ 数据备份与迁移 (跨设备使用)", expanded=False):
        col_ex, col_im = st.columns(2)
        with col_ex:
            st.markdown("**1. 导出数据**")
            # 准备数据
            json_str = json.dumps(st.session_state["favorites"], ensure_ascii=False, indent=2)
            
            # 生成带时间戳的文件名
            file_name = f"nuclear_backup_{st.session_state['user_id']}_{datetime.datetime.now().strftime('%Y%m%d')}.json"
            
            # 下载按钮
            st.download_button(
                label="📥 点击下载备份文件 (.json)",
                data=json_str,
                file_name=file_name,
                mime="application/json",
                use_container_width=True
            )
            
            st.caption("或者手动复制下方代码：")
            st.code(json_str, language="json")
            
        with col_im:
            st.markdown("**2. 恢复数据** (粘贴 JSON 并按回车)")
            restore_str = st.text_input("在此粘贴备份数据", key="restore_input")
            if restore_str:
                if st.button("确认恢复"):
                    try:
                        data = json.loads(restore_str)
                        if isinstance(data, list):
                            st.session_state["favorites"] = data
                            save_favorites()
                            st.success("恢复成功！刷新页面生效。")
                            time.sleep(1)
                            st.rerun()
                    except: st.error("格式错误")

    st.divider()
    
    favs = st.session_state["favorites"]
    if not favs:
        st.info("👋 暂无收藏。请在其他板块点击 '⭐' 按钮添加内容。")
    else:
        st.caption(f"共 {len(favs)} 条记录")
        
        # 遍历显示收藏项 (倒序：最新的在最上面)
        for index, item in enumerate(reversed(favs)):
            # 注意：删除时需要用原始索引或者唯一ID
            
            with st.container():
                # 使用自定义 CSS 框来美化
                col_mark, col_content = st.columns([0.05, 0.95])
                with col_mark:
                    # 左侧彩色条
                    color = "#63b3ed" if item['category'] == "学术文献" else "#66bb6a" if item['category'] == "核查结论" else "#d69e2e"
                    st.markdown(f"<div style='height:100%; min-height: 50px; border-left: 4px solid {color};'>&nbsp;</div>", unsafe_allow_html=True)
                
                with col_content:
                    # 标题栏
                    c_title, c_del = st.columns([9, 1])
                    with c_title:
                        st.markdown(f"**[{item['category']}]** {item['title']}")
                        st.caption(f"🕒 {item['time']}")
                    with c_del:
                        if st.button("🗑️", key=f"del_{item['id']}", help="删除此条"):
                            delete_favorite(item['id'])
                    
                    # 内容详情折叠区
                    with st.expander("查看详情"):
                        content = item['content']
                        
                        # 1. 学术文献 (字典格式)
                        if item['category'] == "学术文献" and isinstance(content, dict):
                            st.markdown(f"**Authors:** {content.get('authors')}")
                            st.info(content.get('summary'))
                            st.markdown(f"[🔗 原文链接]({content.get('url')})")
                        
                        # 2. 核查结论 (字典格式)
                        elif item['category'] == "核查结论" and isinstance(content, dict):
                            st.markdown(f"**状态:** {content.get('status')}")
                            st.warning(f"**分析:** {content.get('correction')}")
                            st.markdown("**证据来源:**")
                            for e in content.get('evidence_list', []):
                                st.markdown(f"- [{e.get('source_name')}]({e.get('url')}): {e.get('content')}")
                        
                        # 3. 改写结果 (字典格式)
                        elif item['category'] == "改写结果" and isinstance(content, dict):
                            st.caption("原始草稿:")
                            st.text(content.get('draft'))
                            st.markdown("---")
                            st.markdown("**改写:**")
                            st.markdown(content.get('rewrite'))
                            if content.get('translation'):
                                st.markdown("**翻译:**")
                                st.markdown(content.get('translation'))
                        
                        # 4. 纯文本/其他
                        else:
                            st.markdown(str(content))
            st.markdown("---")
