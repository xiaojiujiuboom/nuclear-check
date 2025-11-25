import streamlit as st
import requests
import json
import re
import time

# --- 1. 配置区域 ---
# 必须填入你的 Key (请确保该 Key 有权限使用 Google Search Grounding 功能)
API_KEY = "AIzaSyDuW0mTAhwFjEX1_Gnb-LnExvZVpYUzgHk"  

# --- 2. 页面设置 ---
st.set_page_config(page_title="智能核查助手 (Pro Max)", layout="wide", page_icon="⚛️")

# --- CSS 样式优化：适配深色模式 & Tab样式 ---
st.markdown("""
    <style>
        .block-container {padding-top: 2rem;}
        header, footer {visibility: hidden;}
        
        /* -----------------------
           通用深色模式适配
           ----------------------- */
        
        /* 1. 核查卡片 (Check Card) - 保持之前的风格 */
        .check-card {
            border: 1px solid #464b59;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background-color: #262730; 
            color: #FAFAFA;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        /* 2. 学术检索卡片 (Research Card) - 新增风格 */
        .research-card {
            border: 1px solid #4a5568; /* 偏蓝灰 */
            border-left: 5px solid #63b3ed; /* 亮蓝色左边框 */
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background-color: #2d3748; /* 深蓝灰背景 */
            color: #e2e8f0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }

        /* 来源链接样式 - 通用 */
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
        
        /* Sci-Hub 按钮特化样式 */
        .scihub-btn {
            background-color: #2c0b0e; /* 深红色背景 */
            color: #fc8181 !important; /* 浅红文字 */
            border: 1px solid #822727;
        }
        .scihub-btn:hover {
            background-color: #451014;
            color: #feb2b2 !important;
            border-color: #fc8181;
        }

        /* 证据引文容器样式 */
        .evidence-container {
            background-color: #1a202c; /* 更深的背景 */
            border-radius: 6px;
            padding: 12px;
            margin-top: 12px;
            border: 1px solid #2d3748;
        }

        /* 单条证据样式 */
        .quote-item {
            border-left: 3px solid #718096;
            padding-left: 10px;
            margin-bottom: 8px;
            color: #cbd5e0;
            font-size: 0.95em;
            font-family: "Noto Serif SC", serif; /* 学术感字体 */
        }
        
        /* 标签样式 */
        .tag-pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            margin-right: 5px;
            background-color: #4a5568;
            color: #a0aec0;
        }

    </style>
""", unsafe_allow_html=True)

# --- 3. 自动寻找可用模型函数 ---
def get_available_model(api_key):
    """
    寻找支持 generateContent 的模型。
    强制优先使用 gemini-2.5-flash 或 gemini-1.5-flash。
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, f"连接失败: {response.text}"
        
        data = response.json()
        models = data.get('models', [])
        
        model_names = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        if not model_names: return None, "未找到任何可用模型"

        # 优先级匹配逻辑
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

# --- 4. 辅助函数：解析 AI 返回的 JSON ---
def parse_json_response(text):
    try:
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        start = text.find('[')
        end = text.rfind(']') + 1
        if start != -1 and end != -1:
            json_str = text[start:end]
            return json.loads(json_str)
        return None
    except Exception:
        return None

# --- 5. 核心页面逻辑 ---
st.subheader("⚛️ Nuclear Knowledge Hub")
st.caption("核科学事实核查与学术检索")

# 创建两个独立的 Tabs
tab1, tab2 = st.tabs(["🔍 智能核查 (Check)", "🔬 学术检索 (Search)"])

# ==========================================
# 模块一：智能核查 (Nuclear Check)
# ==========================================
with tab1:
    col1_check, col2_check = st.columns([1, 1], gap="large")

    with col1_check:
        user_text_check = st.text_area("待核查文本", height=400, placeholder="例如：中国现在有57座核电站？", key="input_check")
        check_btn = st.button("🚀 开始深度核查", type="primary", use_container_width=True, key="btn_check")

    with col2_check:
        if check_btn and user_text_check:
            if not API_KEY.startswith("AIza"):
                st.error("请先在代码第 8 行填入正确的 API Key")
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
                    
                    # 核查 Prompt
                    prompt_check = f"""
                    你是一个严谨的核聚变与等离子体物理专家，同时拥有实时联网核查的能力。
                    请利用 Google Search 工具，核查以下文本中的每一个事实陈述。

                    **用户输入文本：**
                    '''{user_text_check}'''

                    **重要指示：**
                    1. **多源数据对比**：如果不同权威机构的数据不一致（例如 IAEA 数据 vs 中国核能行业协会数据），**请不要只给出一个数字**，而必须将各方数据分别列出。
                    2. **原文引用**：对于每一个数据点，必须引用查找资料的原话。
                    3. **实时性**：以搜索到的最新官方报告为准。

                    请输出一个纯 JSON 列表。每个对象结构如下：
                    {{
                        "claim": "原文中的陈述",
                        "status": "正确/错误/存疑/数据不一致",
                        "correction": "综合分析。如果数据冲突，请在此说明差异原因。",
                        "evidence_list": [
                            {{
                                "source_name": "机构名称",
                                "content": "具体描述/数据",
                                "url": "来源链接"
                            }}
                        ]
                    }}
                    """
                    
                    payload = {
                        "contents": [{"parts": [{ "text": prompt_check }]}],
                        "tools": [{"google_search": {}}]
                    }
                    
                    status_box.write("🔍 正在联网检索最新权威数据 (IAEA/NEA/CNEA)...")
                    
                    try:
                        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
                        
                        if response.status_code == 200:
                            result = response.json()
                            try:
                                candidates = result.get('candidates', [])
                                if not candidates: raise ValueError("无候选项")
                                content_parts = candidates[0].get('content', {}).get('parts', [])
                                raw_content = content_parts[0].get('text', "") if content_parts else ""
                                
                                check_results = parse_json_response(raw_content)
                                
                                status_box.update(label="深度核查完成", state="complete", expanded=False)
                                
                                if check_results:
                                    st.success(f"核查完成！已比对多方权威数据源")
                                    
                                    for item in check_results:
                                        status = item.get('status', '存疑')
                                        # 样式逻辑
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
                                                st.markdown('<div style="color: #8ab4f8; margin-bottom: 8px; font-weight:bold;">🔍 权威数据/原文证据：</div>', unsafe_allow_html=True)
                                                
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
        search_query = st.text_input("请输入研究课题、关键词或问题", placeholder="例如：可控核聚变 2024年 突破性进展 Q值", key="input_search")
        st.caption("支持中英文输入。系统将自动检索数据库。")
        search_btn = st.button("🔬 开始学术检索", type="primary", use_container_width=True, key="btn_search")

    with col2_search:
        if search_btn and search_query:
            if not API_KEY.startswith("AIza"):
                st.error("API Key 无效")
            else:
                status_box_search = st.status("正在进行深度学术检索...", expanded=True)
                
                model_name, _ = get_available_model(API_KEY)
                if model_name:
                    if not model_name.startswith("models/"): model_name = f"models/{model_name}"
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
                    
                    # 学术检索 Prompt (升级版 - 防幻觉)
                    prompt_search = f"""
                    你是一位资深的核科学研究员。请利用 Google Search 为用户寻找**真实存在**的学术文献。
                    
                    **用户课题：** "{search_query}"
                    
                    **严厉禁止 (Anti-Hallucination)：**
                    1. **严禁编造**论文标题、作者、期刊或链接。
                    2. **严禁拼凑**不同来源的信息（例如：用A论文的标题配B论文的链接）。
                    3. 如果搜索结果中没有提供PDF链接或DOI，**请留空**，不要根据经验猜测 URL。
                    
                    **执行步骤：**
                    1. 使用 Google Search 搜索相关的高质量学术来源（Nature, Science, IAEA, ITER, PRL等）。
                    2. 从搜索结果的 Snippets 中**提取**文献信息。
                    3. **链接(url)** 必须直接来自搜索结果中的真实网址，确保可访问。
                    
                    **输出格式：**
                    请输出一个纯 JSON 列表。如果找不到确切的学术论文，可以返回相关的权威新闻或技术报告。
                    每个对象结构如下：
                    {{
                        "title": "标题 (必须完全匹配搜索结果)",
                        "authors": "作者/机构 (仅提取搜索结果中显示的)",
                        "publication": "来源 (如 Nature, IAEA)",
                        "year": "年份",
                        "summary": "基于搜索摘要的简述",
                        "doi": "仅在搜索结果中明确看到DOI时填写，否则为空字符串",
                        "url": "搜索结果对应的真实URL"
                    }}
                    """
                    
                    payload = {
                        "contents": [{"parts": [{ "text": prompt_search }]}],
                        "tools": [{"google_search": {}}]
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
                                
                                search_results = parse_json_response(raw_content)
                                
                                status_box_search.update(label="检索完成", state="complete", expanded=False)
                                
                                if search_results:
                                    st.success(f"检索到 {len(search_results)} 篇相关高价值文献")
                                    
                                    for item in search_results:
                                        title = item.get('title', '未知标题')
                                        doi = item.get('doi', '')
                                        url = item.get('url', '#')
                                        
                                        with st.container():
                                            # 学术卡片头部
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
                                            
                                            # 操作按钮区
                                            col_links = st.columns([1, 1, 4])
                                            
                                            # 1. 原文链接
                                            st.markdown(f'<a href="{url}" target="_blank" class="source-link">🔗 原文/Abstract</a>', unsafe_allow_html=True)
                                            
                                            # 2. Sci-Hub 下载按钮 (如果有 DOI)
                                            if doi and len(doi) > 5: # 简单过滤无效DOI
                                                scihub_url = f"https://x.sci-hub.org.cn/{doi}"
                                                st.markdown(f'<a href="{scihub_url}" target="_blank" class="source-link scihub-btn">🔓 Sci-Hub 下载</a>', unsafe_allow_html=True)
                                            
                                            st.markdown("</div>", unsafe_allow_html=True)
                                else:
                                    st.warning("未能解析搜索结果，以下是原始回答：")
                                    st.markdown(raw_content)
                                    
                            except Exception as e:
                                st.error(f"解析错误: {e}")
                        else:
                            st.error(f"请求失败: {response.status_code}")
                            
                    except Exception as e:
                        st.error(f"网络错误: {e}")