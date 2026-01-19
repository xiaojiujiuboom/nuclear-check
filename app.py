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

# --- 3. CSS 样式优化 ---
st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* 通用深色模式适配 */
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
        
        /* 学术综述卡片样式 */
        .overview-card {
            border: 1px solid #5a4b81; 
            border-left: 5px solid #9f7aea; /* 紫色系 */
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            background-color: #322659; /* 深紫色背景 */
            color: #e9d8fd;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }

        /* 新增：学术改写卡片样式 */
        .rewrite-card {
            border: 1px solid #285e61;
            border-left: 5px solid #38b2ac; /* 青色系 */
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 1.0rem;
            background-color: #234e52; /* 深青色背景 */
            color: #e6fffa;
            font-family: "Noto Serif SC", serif; /* 使用衬线字体增加学术感 */
            line-height: 1.8;
            font-size: 1.05rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        /* 翻译部分样式 */
        .translation-section {
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px dashed #4fd1c5;
            color: #b2f5ea;
            font-size: 0.95rem;
            font-style: italic;
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

        /* 证据容器样式 (浅色背景 + 深色文字) */
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

# --- 4. 自动寻找可用模型函数 ---
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

        # 优先级匹配逻辑 (更新为最新模型)
        preferred_order = [
            'gemini-2.5-flash-preview', # 最新预览版
            'gemini-2.0-flash-exp',     # 实验版 (俗称的下一代)
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-1.5-pro'
        ]

        selected_model = None
        for pref in preferred_order:
            for available_model in model_names:
                # 模糊匹配模型名称
                if pref in available_model: 
                    selected_model = available_model
                    break
            if selected_model: break
        
        if not selected_model:
            selected_model = model_names[0]

        return selected_model, "Success"

    except Exception as e:
        return None, str(e)

# --- 5. 辅助函数：解析 AI 返回的 JSON ---
def parse_json_response(text):
    """
    增强版解析器：
    1. 优先尝试直接 JSON.loads (对应 Native JSON Mode)
    2. 其次尝试去除 Markdown 标记
    3. 最后尝试提取 { ... } 或 [ ... ]
    """
    try:
        # 1. 尝试直接解析 (适用于 Native JSON Mode 返回的纯净数据)
        return json.loads(text)
    except:
        pass

    try:
        # 2. 清理 Markdown 标记
        clean_text = re.sub(r'```json\s*', '', text)
        clean_text = re.sub(r'```\s*$', '', clean_text)
        clean_text = clean_text.strip()
        return json.loads(clean_text)
    except Exception:
        # 3. 尝试提取 {} 或 [] 区间
        try:
            start_obj = text.find('{')
            start_list = text.find('[')
            
            if start_obj != -1 and (start_list == -1 or start_obj < start_list):
                # 这是一个对象
                end = text.rfind('}') + 1
                return json.loads(text[start_obj:end])
            elif start_list != -1:
                # 这是一个列表
                end = text.rfind(']') + 1
                return json.loads(text[start_list:end])
            return None
        except:
            return None

# --- 6. 核心页面逻辑 ---
# 侧边栏
with st.sidebar:
    st.title("⚛️ Nuclear Hub")
    st.info(
        """
        **版本**: Pro Max v2.8 (Stable)
        
        本平台优先接入 **Gemini 2.5 Flash / 2.0 Flash**，
        并启用了 **Native JSON Mode** 以确保检索稳定性。
        """
    )
    st.caption("Powered by Google Gemini & Streamlit")

st.title("Nuclear Knowledge Hub")
st.caption("🚀 核科学事实核查、学术检索与专业改写平台")

# 创建三个独立的 Tabs
tab1, tab2, tab3 = st.tabs(["🔍 智能核查 (Check)", "🔬 学术检索 (Search)", "✍️ 学术改写 (Rewrite)"])

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
        if check_btn and user_text_check:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key，或者在 Secrets 中配置。")
            else:
                status_box = st.status("正在启动核查引擎...", expanded=True)
                
                status_box.write("正在连接 Google Gemini 节点...")
                model_name, msg = get_available_model(API_KEY)
                
                if not model_name:
                    status_box.update(label="初始化失败", state="error")
                    st.error(f"无法获取模型列表: {msg}")
                else:
                    if not model_name.startswith("models/"): model_name = f"models/{model_name}"
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
                    
                    # --- 核查 Prompt ---
                    prompt_check = f"""
                    你是一个严谨的核聚变与等离子体物理专家，同时拥有实时联网核查的能力。
                    请利用 Google Search 工具，核查以下文本中的每一个事实陈述。

                    **用户输入文本：**
                    '''{user_text_check}'''

                    **重要指示：**
                    1. **多源数据对比**：如果不同权威机构的数据不一致（例如 IAEA 数据 vs 中国核能行业协会数据），**请不要只给出一个数字**，而必须将各方数据分别列出。
                    2. **原文引用 (双语)**：
                       - 对于每一个数据点，必须引用查找资料的原话。
                       - **关键要求**：如果引用的原文是英文，**必须**在后面附带中文翻译。
                       - 格式示例："The reactor has... (译文: 该反应堆拥有...)"。
                    3. **实时性**：以搜索到的最新官方报告为准。

                    请输出一个纯 JSON 列表。每个对象结构如下：
                    {{
                        "claim": "原文中的陈述",
                        "status": "正确/错误/存疑/数据不一致",
                        "correction": "综合分析。如果数据冲突，请在此说明差异原因。",
                        "evidence_list": [
                            {{
                                "source_name": "机构名称",
                                "content": "具体描述/数据 (如果是英文请附带中文翻译)",
                                "url": "来源链接"
                            }}
                        ]
                    }}
                    """
                    
                    # 启用 Native JSON Mode
                    payload = {
                        "contents": [{"parts": [{ "text": prompt_check }]}],
                        "tools": [{"google_search": {}}],
                        "generationConfig": {
                            "responseMimeType": "application/json"
                        }
                    }
                    
                    status_box.write("🔍 正在联网检索最新数据...")
                    
                    try:
                        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
                        
                        if response.status_code == 200:
                            result = response.json()
                            try:
                                candidates = result.get('candidates', [])
                                if not candidates: raise ValueError("无候选项")
                                content_parts = candidates[0].get('content', {}).get('parts', [])
                                raw_content = content_parts[0].get('text', "") if content_parts else ""
                                
                                # 使用增强版解析器
                                check_results = parse_json_response(raw_content)
                                
                                status_box.update(label="深度核查完成", state="complete", expanded=False)
                                
                                if check_results:
                                    st.success(f"核查完成！已比对多方权威数据源")
                                    
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
                                            # 兼容性处理
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
                                    st.warning("AI 返回的内容无法解析")
                                    st.markdown(raw_content)

                            except Exception as e:
                                status_box.update(label="解析失败", state="error")
                                st.error(f"解析错误: {e}")
                        else:
                            st.error(f"API 请求失败: {response.status_code}")
                    except Exception as e:
                        st.error(f"网络连接错误: {e}")

# ==========================================
# 模块二：学术检索 (Nuclear Search)
# ==========================================
with tab2:
    col1_search, col2_search = st.columns([1, 1], gap="large")
    
    with col1_search:
        st.markdown("#### 🔍 学术搜索引擎")
        search_query = st.text_input("请输入研究课题、关键词或问题", label_visibility="collapsed", placeholder="例如：可控核聚变 2024年 突破性进展 Q值", key="input_search")
        st.caption("支持中英文输入。系统将自动检索数据库。")
        search_btn = st.button("🔬 开始学术检索", type="primary", use_container_width=True, key="btn_search")

    with col2_search:
        st.markdown("#### 📚 检索结果")
        if search_btn and search_query:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key，或者在 Secrets 中配置。")
            else:
                status_box_search = st.status("正在进行深度学术检索...", expanded=True)
                
                model_name, _ = get_available_model(API_KEY)
                if model_name:
                    if not model_name.startswith("models/"): model_name = f"models/{model_name}"
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
                    
                    # --- 学术检索 Prompt ---
                    prompt_search = f"""
                    你是一位资深的核科学研究员。请利用 Google Search 为用户寻找**真实存在**的学术文献。
                    
                    **用户课题：** "{search_query}"
                    
                    **任务 (两部分)：**
                    1. **Overview (综述)**: 基于搜索到的所有文献，用中文写一段 150 字左右的学术综述，总结该领域的最新进展或回答用户问题。
                    2. **Papers (文献列表)**: 列出具体的文献。
                    
                    **严厉禁止 (Anti-Hallucination)：**
                    1. **严禁编造**论文标题、作者、期刊或链接。
                    2. 如果没有PDF链接或DOI，请留空。
                    
                    **执行步骤：**
                    1. 搜索 Nature, Science, IAEA, ITER, PRL 等来源。
                    2. 提取信息，确保链接真实。
                    3. 编写综述。
                    
                    **输出格式：**
                    请输出一个包含两个字段的纯 JSON 对象：
                    {{
                        "overview": "这里写中文综述，总结研究现状...",
                        "papers": [
                            {{
                                "title": "标题 (必须完全匹配搜索结果，如果是英文，请在括号内附上中文翻译)",
                                "authors": "作者/机构",
                                "publication": "来源 (如 Nature, IAEA)",
                                "year": "年份",
                                "summary": "详细摘要 (请保留英文原文，并在后面附带中文翻译)",
                                "doi": "DOI或空字符串",
                                "url": "真实URL"
                            }}
                        ]
                    }}
                    """
                    
                    # 启用 Native JSON Mode - 这是解决"未能解析"的关键
                    payload = {
                        "contents": [{"parts": [{ "text": prompt_search }]}],
                        "tools": [{"google_search": {}}],
                        "generationConfig": {
                            "responseMimeType": "application/json"
                        }
                    }
                    
                    status_box_search.write("🔍 正在连接 Google Scholar & 权威期刊库...")
                    
                    try:
                        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            try:
                                candidates = result.get('candidates', [])
                                content_parts = candidates[0].get('content', {}).get('parts', [])
                                raw_content = content_parts[0].get('text', "") if content_parts else ""
                                
                                # 解析 JSON
                                search_results = parse_json_response(raw_content)
                                
                                status_box_search.update(label="检索完成", state="complete", expanded=False)
                                
                                if search_results:
                                    # 处理两种可能的数据结构
                                    papers = []
                                    overview = ""
                                    
                                    if isinstance(search_results, dict):
                                        papers = search_results.get('papers', [])
                                        overview = search_results.get('overview', "")
                                    elif isinstance(search_results, list):
                                        papers = search_results
                                    
                                    # --- 1. 展示学术综述 (Overview) ---
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

                                    # --- 2. 展示文献列表 ---
                                    if papers:
                                        st.success(f"检索到 {len(papers)} 篇相关高价值文献")
                                        
                                        for item in papers:
                                            title = item.get('title', '未知标题')
                                            doi = item.get('doi', '')
                                            url = item.get('url', '#')
                                            
                                            with st.container():
                                                st.markdown(f"""
                                                <div class="research-card">
                                                    <div style="font-size: 1.2em; font-weight: bold; color: #63b3ed; margin-bottom: 5px;">
                                                        📄 {title}
                                                    </div>
                                                    <div style="font-size: 0.9em; color: #a0aec0; margin-bottom: 15px;">
                                                        <span style="color: #e2e8f0;">{item.get('authors', '未知作者')}</span> | 
                                                        <span style="font-style: italic;">{item.get('publication', '未知来源')}</span>, {item.get('year', 'N/A')}
                                                    </div>
                                                    <div style="border-top: 1px solid #4a5568; margin-bottom: 10px;"></div>
                                                    <div style="line-height: 1.6; color: #cbd5e0; font-family: 'Noto Serif SC', serif;">
                                                        {item.get('summary', '暂无摘要')}
                                                    </div>
                                                """, unsafe_allow_html=True)
                                                
                                                col_links = st.columns([1, 1, 4])
                                                st.markdown(f'<a href="{url}" target="_blank" class="source-link">🔗 原文/Abstract</a>', unsafe_allow_html=True)
                                                if doi and len(doi) > 5:
                                                    scihub_url = f"https://x.sci-hub.org.cn/{doi}"
                                                    st.markdown(f'<a href="{scihub_url}" target="_blank" class="source-link scihub-btn">🔓 Sci-Hub 下载</a>', unsafe_allow_html=True)
                                                st.markdown("</div>", unsafe_allow_html=True)
                                    else:
                                        st.warning("未找到具体的文献列表，但已生成综述。")
                                else:
                                    st.warning("未能解析搜索结果")
                                    st.markdown(raw_content)
                            except Exception as e:
                                st.error(f"解析错误: {e}")
                        else:
                            st.error(f"请求失败: {response.status_code}")
                    except Exception as e:
                        st.error(f"网络错误: {e}")

# ==========================================
# 模块三：学术改写 (Academic Rewrite)
# ==========================================
with tab3:
    col1_rewrite, col2_rewrite = st.columns([1, 1], gap="large")

    with col1_rewrite:
        st.markdown("#### ✍️ 原始草稿")
        user_text_rewrite = st.text_area(
            "待改写文本", 
            height=500, 
            label_visibility="collapsed", 
            placeholder="请在此粘贴您的论文草稿、段落或句子...\n系统将优化逻辑、词汇与句式，使其符合高水平发表标准。", 
            key="input_rewrite"
        )
        rewrite_btn = st.button("✨ 开始学术改写", type="primary", use_container_width=True, key="btn_rewrite")

    with col2_rewrite:
        st.markdown("#### 🖋️ 改写结果")
        if rewrite_btn and user_text_rewrite:
            if not API_KEY:
                st.error("🔒 请在侧边栏输入 API Key")
            else:
                status_box_rewrite = st.status("正在进行语言润色与逻辑重构...", expanded=True)
                model_name, _ = get_available_model(API_KEY)
                
                if model_name:
                    if not model_name.startswith("models/"): model_name = f"models/{model_name}"
                    
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"

                    # --- 升级版学术改写 Prompt (保持文本模式，不强制JSON) ---
                    prompt_rewrite = f"""
                    你是一位在高级核杂质期刊有丰富经验的**人类学术编辑**。
                    请对以下文本进行**彻底的去AI化（De-AI）改写**，并提供双语对照。

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
                    
                    **✅可以参考学习模仿以下写作风格：**
                     1.  "Direct drive means conducting electrons as the energy to create a reaction, usually in the form of laser beams..." (简洁直接的定义)
                     2.  "In this work, we present the results of an experiment aiming at proton acceleration using a focus with a homogeneous intensity distribution..." (清晰的实验叙述)
                     3.  "The interaction of ultraintense laser pulses with solids is largely affected by the plasma gradient..." (因果逻辑清晰)

                    **输出格式（必须严格遵守）：**
                    请按以下标签分隔内容：

                    [REWRITE]
                    (这里是改写后的优美学术文本)

                    [TRANSLATION]
                    (这里是对应的另一种语言的高水平翻译)
                    """

                    payload = {
                        "contents": [{"parts": [{ "text": prompt_rewrite }]}]
                        # 注意：此处不开启 JSON 模式，因为我们需要特定格式的文本块
                    }

                    try:
                        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            candidates = result.get('candidates', [])
                            content_parts = candidates[0].get('content', {}).get('parts', [])
                            full_text = content_parts[0].get('text', "") if content_parts else ""
                            
                            status_box_rewrite.update(label="润色完成", state="complete", expanded=False)
                            
                            if full_text:
                                # 解析 [REWRITE] 和 [TRANSLATION]
                                rewrite_content = full_text
                                translation_content = ""
                                
                                if "[REWRITE]" in full_text and "[TRANSLATION]" in full_text:
                                    parts = full_text.split("[TRANSLATION]")
                                    rewrite_part = parts[0].replace("[REWRITE]", "").strip()
                                    translation_part = parts[1].strip()
                                    
                                    rewrite_content = rewrite_part
                                    translation_content = translation_part
                                else:
                                    # Fallback
                                    rewrite_content = full_text.replace("[REWRITE]", "").replace("[TRANSLATION]", "")

                                translation_html = ""
                                if translation_content:
                                    translation_html = f"""<div class="translation-section"><div style="margin-bottom: 8px; font-weight: bold;">🌐 Translation:</div>{translation_content.replace(chr(10), '<br>')}</div>"""

                                st.markdown(f"""
                                <div class="rewrite-card">
                                    <div style="margin-bottom: 10px; font-weight: bold; color: #81e6d9;">🖋️ Revised Text:</div>
                                    {rewrite_content.replace(chr(10), '<br>')}
                                    {translation_html}
                                </div>
                                """, unsafe_allow_html=True)
                                
                            else:
                                st.error("生成内容为空，请重试。")
                        else:
                            st.error(f"API 请求失败: {response.status_code}")
                    except Exception as e:
                        st.error(f"连接错误: {e}")
