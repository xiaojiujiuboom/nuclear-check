import streamlit as st
import requests
import json
import re
import time

# --- 1. 页面配置 (必须在最前面) ---
st.set_page_config(
    page_title="Nuclear Knowledge Hub", 
    layout="wide", 
    page_icon="⚛️",
    initial_sidebar_state="expanded"
)

# --- 2. 获取 API Key ---
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
        API_KEY = st.text_input("请在此临时粘贴 API Key:", type="password", help="建议在 Streamlit Secrets 中配置 GEMINI_API_KEY。")

# --- 3. CSS 样式 ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        .check-card {
            border: 1px solid #464b59;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background-color: #262730; 
            color: #FAFAFA;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        .research-card {
            border: 1px solid #4a5568; 
            border-left: 5px solid #63b3ed;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background-color: #2d3748; 
            color: #e2e8f0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        .overview-card {
            border: 1px solid #5a4b81; 
            border-left: 5px solid #9f7aea;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            background-color: #322659;
            color: #e9d8fd;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }

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
    </style>
""", unsafe_allow_html=True)

# --- 4. 自动寻找可用模型 ---
def get_available_model(api_key):
    if not api_key: return None, "API Key 未配置"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, f"连接失败: {response.text}"
        
        data = response.json()
        models = data.get('models', [])
        
        model_names = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        if not model_names: return None, "未找到任何可用模型"

        preferred_order = [
            'gemini-2.5-flash',
            'gemini-1.5-flash',
            'gemini-1.5-flash-latest',
            'gemini-1.5-pro'
        ]

        selected_model = None
        for pref in preferred_order:
            for available_model in model_names:
                if pref in available_model: 
                    selected_model = available_model
                    break
            if selected_model: break
        
        if not selected_model:
            selected_model = model_names[0]

        return selected_model, "Success"

    except Exception as e:
        return None, str(e)

# --- 5. JSON 解析函数 ---
def parse_json_response(text):
    try:
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        text = text.strip()
        
        return json.loads(text)
    except Exception:
        try:
            start_obj = text.find('{')
            start_list = text.find('[')
            
            if start_obj != -1 and (start_list == -1 or start_obj < start_list):
                end = text.rfind('}') + 1
                return json.loads(text[start_obj:end])
            elif start_list != -1:
                end = text.rfind(']') + 1
                return json.loads(text[start_list:end])
            return None
        except:
            return None

# --- 6. 主逻辑 ---
with st.sidebar:
    st.title("⚛️ Nuclear Hub")
    st.info("**版本**: Pro Max v2.4 (Fix URL & Trans)")
    st.caption("Powered by Google Gemini & Streamlit")

st.title("Nuclear Knowledge Hub")
st.caption("🚀 核科学事实核查与学术检索平台")

tab1, tab2 = st.tabs(["🔍智能核查 (Check)", "🔬学术检索 (Search)"])

# ==========================================
# 模块一：智能核查
# ==========================================
with tab1:
    col1_check, col2_check = st.columns([1, 1], gap="large")

    with col1_check:
        st.markdown("#### 📝 输入待核查内容")
        user_text_check = st.text_area("待核查文本", height=400, label_visibility="collapsed", placeholder="例如：中国现在有58座核电站？", key="input_check")
        check_btn = st.button("🚀 开始深度核查", type="primary", use_container_width=True, key="btn_check")

    with col2_check:
        st.markdown("#### 📊 核查报告")
        if check_btn and user_text_check:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key")
            else:
                status_box = st.status("正在启动核查引擎...", expanded=True)
                model_name, msg = get_available_model(API_KEY)
                
                if not model_name:
                    status_box.update(label="初始化失败", state="error")
                    st.error(f"无法获取模型列表: {msg}")
                else:
                    if not model_name.startswith("models/"): model_name = f"models/{model_name}"
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
                    
                    prompt_check = f"""
                    你是一个严谨的核聚变与等离子体物理专家。请利用 Google Search 工具核查以下文本。

                    **文本：** '''{user_text_check}'''

                    **关键要求：**
                    1. **多源数据**：如果数据冲突（如 IAEA vs 官方），必须列出各方数据。
                    2. **强制翻译引用**：
                       - 必须引用查找资料的原话。
                       - **如果原文是英文，必须在后面紧跟中文翻译**。
                       - 格式："...English text... (译文: ...中文...)"

                    **输出格式 (JSON List):**
                    [
                        {{
                            "claim": "原文陈述",
                            "status": "正确/错误/存疑/数据不一致",
                            "correction": "综合分析",
                            "evidence_list": [
                                {{
                                    "source_name": "机构名",
                                    "content": "原文证据 (若为英文需附翻译)",
                                    "url": "链接"
                                }}
                            ]
                        }}
                    ]
                    """
                    
                    payload = {
                        "contents": [{"parts": [{ "text": prompt_check }]}],
                        "tools": [{"google_search": {}}]
                    }
                    
                    status_box.write("🔍 正在联网检索...")
                    
                    try:
                        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
                        
                        if response.status_code == 200:
                            result = response.json()
                            try:
                                candidates = result.get('candidates', [])
                                content_parts = candidates[0].get('content', {}).get('parts', [])
                                raw_content = content_parts[0].get('text', "") if content_parts else ""
                                check_results = parse_json_response(raw_content)
                                
                                status_box.update(label="核查完成", state="complete", expanded=False)
                                
                                if check_results:
                                    st.success(f"核查完成！")
                                    for item in check_results:
                                        status = item.get('status', '存疑')
                                        if "错" in status:
                                            border_color = "#ff4b4b"
                                            icon = "❌"
                                            title_color = "#ff8a80"
                                        elif "疑" in status or "不一致" in status:
                                            border_color = "#ffa726"
                                            icon = "⚠️"
                                            title_color = "#ffcc80"
                                        else:
                                            border_color = "#66bb6a"
                                            icon = "✅"
                                            title_color = "#a5d6a7"
                                        
                                        with st.container():
                                            st.markdown(f"""
                                            <div class="check-card" style="border-left: 5px solid {border_color};">
                                                <div style="margin-bottom: 12px;">
                                                    <span style="font-weight: bold; font-size: 1.3em; color: {title_color};">{icon} {status}</span>
                                                    <div style="color: #b0bec5; font-size: 0.9em; margin-top: 4px;">陈述：{item.get('claim', '')}</div>
                                                </div>
                                                <div style="margin-bottom: 15px; line-height: 1.6;">
                                                    <b>💡 专家分析：</b><br>
                                                    {item.get('correction', '无详细分析')}
                                                </div>
                                            """, unsafe_allow_html=True)
                                            
                                            evidence_list = item.get('evidence_list', [])
                                            # 兼容旧格式
                                            if not evidence_list and 'evidence_quote' in item:
                                                evidence_list = [{'source_name': '权威数据', 'content': item['evidence_quote'], 'url': '#'}]

                                            if evidence_list:
                                                st.markdown('<div class="evidence-container">', unsafe_allow_html=True)
                                                st.markdown('<div style="color: #555; margin-bottom: 8px; font-weight:bold;">🔍 权威数据/原文证据：</div>', unsafe_allow_html=True)
                                                for ev in evidence_list:
                                                    source_name = ev.get('source_name', '来源')
                                                    content = ev.get('content', '')
                                                    url = ev.get('url', '#')
                                                    st.markdown(f"""
                                                    <div class="quote-item">
                                                        <span class="tag-pill">[{source_name}]</span>
                                                        "{content}"
                                                        <br>
                                                        <a href="{url}" target="_blank" class="source-link" style="margin-top:4px; display:inline-block;">🔗 来源</a>
                                                    </div>
                                                    """, unsafe_allow_html=True)
                                                st.markdown('</div>', unsafe_allow_html=True)
                                            st.markdown("</div>", unsafe_allow_html=True)
                                else:
                                    st.warning("解析失败")
                                    st.markdown(raw_content)
                            except Exception as e:
                                st.error(f"解析错误: {e}")
                        else:
                            st.error(f"API 请求失败: {response.status_code}")
                    except Exception as e:
                        st.error(f"网络错误: {e}")

# ==========================================
# 模块二：学术检索 (重点修复链接与翻译)
# ==========================================
with tab2:
    col1_search, col2_search = st.columns([1, 1], gap="large")
    
    with col1_search:
        st.markdown("#### 🔍 学术搜索引擎")
        search_query = st.text_input("请输入研究课题", label_visibility="collapsed", placeholder="例如：可控核聚变 2024年 突破性进展 Q值", key="input_search")
        search_btn = st.button("🔬 开始学术检索", type="primary", use_container_width=True, key="btn_search")

    with col2_search:
        st.markdown("#### 📚 检索结果")
        if search_btn and search_query:
            if not API_KEY:
                st.error("🔒 请输入 API Key")
            else:
                status_box_search = st.status("正在进行深度学术检索...", expanded=True)
                
                model_name, _ = get_available_model(API_KEY)
                if model_name:
                    if not model_name.startswith("models/"): model_name = f"models/{model_name}"
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
                    
                    # --- 核心修改：防幻觉 Prompt + 强制分离翻译字段 ---
                    prompt_search = f"""
                    你是一位核科学研究员。请利用 Google Search 寻找真实文献。
                    
                    **用户课题：** "{search_query}"
                    
                    **严格指令 (Anti-Hallucination):**
                    1. **链接真实性校验**：
                       - 你输出的 `url` 必须**严格等于**搜索结果中提供的 Snippet URL。
                       - **严禁**自己拼凑链接（不要猜测 nature.com/articles/... 这种链接，除非搜索结果里明确写了）。
                       - 如果搜索结果里没有直接的论文链接，就不要列出那条结果。
                    
                    2. **强制翻译 (Mandatory Translation)**：
                       - JSON中必须包含 `title_en` (原标题) 和 `title_zh` (中文翻译) 两个独立字段。
                       - JSON中必须包含 `summary_zh` (中文摘要)。不要写英文摘要。

                    **输出格式 (JSON Object):**
                    {{
                        "overview": "150字左右的中文综述，总结该领域的最新进展...",
                        "papers": [
                            {{
                                "title_en": "English Title strictly from search result",
                                "title_zh": "这里写中文翻译",
                                "authors": "Author/Institution",
                                "publication": "Source (e.g. Nature)",
                                "year": "Year",
                                "summary_zh": "这里写详细的中文摘要",
                                "doi": "DOI or empty string",
                                "url": "MUST be the EXACT URL from the search snippet"
                            }}
                        ]
                    }}
                    """
                    
                    payload = {
                        "contents": [{"parts": [{ "text": prompt_search }]}],
                        "tools": [{"google_search": {}}]
                    }
                    
                    status_box_search.write("🔍 正在检索并校验链接有效性...")
                    
                    try:
                        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            try:
                                candidates = result.get('candidates', [])
                                content_parts = candidates[0].get('content', {}).get('parts', [])
                                raw_content = content_parts[0].get('text', "") if content_parts else ""
                                search_results = parse_json_response(raw_content)
                                
                                status_box_search.update(label="检索完成", state="complete", expanded=False)
                                
                                if search_results:
                                    papers = []
                                    overview = ""
                                    if isinstance(search_results, dict):
                                        papers = search_results.get('papers', [])
                                        overview = search_results.get('overview', "")
                                    elif isinstance(search_results, list):
                                        papers = search_results
                                    
                                    # 1. 综述
                                    if overview:
                                        with st.container():
                                            st.markdown(f"""
                                            <div class="overview-card">
                                                <div style="font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">
                                                    🧪 学术综述 (Overview)
                                                </div>
                                                <div style="line-height: 1.6; font-size: 1.0em;">
                                                    {overview}
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                    # 2. 文献列表
                                    if papers:
                                        st.success(f"检索到 {len(papers)} 篇相关高价值文献")
                                        for item in papers:
                                            # 获取字段，优先使用分立的翻译字段
                                            title_en = item.get('title_en', item.get('title', 'Unknown Title'))
                                            title_zh = item.get('title_zh', '')
                                            summary = item.get('summary_zh', item.get('summary', '暂无摘要'))
                                            
                                            # 组合标题显示
                                            display_title = title_en
                                            if title_zh:
                                                display_title = f"{title_en}<br><span style='font-size:0.8em; color:#a0aec0; font-weight:normal'>{title_zh}</span>"
                                            
                                            doi = item.get('doi', '')
                                            url = item.get('url', '#')
                                            
                                            with st.container():
                                                st.markdown(f"""
                                                <div class="research-card">
                                                    <div style="font-size: 1.2em; font-weight: bold; color: #63b3ed; margin-bottom: 5px; line-height: 1.4;">
                                                        📄 {display_title}
                                                    </div>
                                                    <div style="font-size: 0.9em; color: #a0aec0; margin-bottom: 15px;">
                                                        <span style="color: #e2e8f0;">{item.get('authors', '未知作者')}</span> | 
                                                        <span style="font-style: italic;">{item.get('publication', '未知来源')}</span>, {item.get('year', 'N/A')}
                                                    </div>
                                                    <div style="border-top: 1px solid #4a5568; margin-bottom: 10px;"></div>
                                                    <div style="line-height: 1.6; color: #cbd5e0; font-family: 'Noto Serif SC', serif;">
                                                        {summary}
                                                    </div>
                                                """, unsafe_allow_html=True)
                                                
                                                col_links = st.columns([1, 1, 4])
                                                st.markdown(f'<a href="{url}" target="_blank" class="source-link">🔗 原文链接/Source</a>', unsafe_allow_html=True)
                                                if doi and len(doi) > 5:
                                                    scihub_url = f"https://x.sci-hub.org.cn/{doi}"
                                                    st.markdown(f'<a href="{scihub_url}" target="_blank" class="source-link scihub-btn">🔓 Sci-Hub 下载</a>', unsafe_allow_html=True)
                                                st.markdown("</div>", unsafe_allow_html=True)
                                    else:
                                        st.warning("未找到具体的文献列表。")
                                else:
                                    st.warning("解析失败")
                                    st.markdown(raw_content)
                            except Exception as e:
                                st.error(f"解析错误: {e}")
                        else:
                            st.error(f"请求失败: {response.status_code}")
                    except Exception as e:
                        st.error(f"网络错误: {e}")
