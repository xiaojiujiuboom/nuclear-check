import streamlit as st
import requests
import json
import re
import time
import ast # 新增：用于处理类 Python 字典格式
import datetime # 新增：用于记录收藏时间

# --- 1. 页面配置 (必须在最前面) ---
st.set_page_config(
    page_title="Nuclear Knowledge Hub", 
    layout="wide", 
    page_icon="⚛️",
    initial_sidebar_state="expanded"
)

# --- 初始化 Session State (用于状态保持和收藏夹) ---
if "favorites" not in st.session_state:
    st.session_state["favorites"] = []

# 用于保持各板块的结果，防止点击按钮后结果消失
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

        /* 学术改写卡片样式 */
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
        
        /* 收藏卡片样式 */
        .fav-card {
            border: 1px solid #d69e2e;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            background-color: #2b2518;
            color: #ecc94b;
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

# --- 4. 核心函数：获取模型轮换列表 (Model Rotation) ---
def get_prioritized_models(api_key):
    """
    返回一个按优先级排序的可用模型列表。
    策略：优先使用稳定且配额高的 1.5-flash，其次是 2.0/2.5 等预览版。
    """
    if not api_key: return [], "API Key 未配置"
    # 修复 URL 格式错误
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return [], f"连接失败: {response.text}"
        
        data = response.json()
        models = data.get('models', [])
        
        # 筛选出支持生成的模型
        available_names = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        if not available_names: return [], "未找到任何可用模型"

        # 定义优先级：稳定版 > 预览版 > 实验版
        # 1.5-flash 通常有最高的 RPM (每分钟请求数)，所以放在前面保底
        priority_keywords = [
            'gemini-1.5-flash',
            'gemini-1.5-flash-8b',
            'gemini-2.0-flash',
            'gemini-2.5-flash',
            'gemini-1.5-pro'
        ]

        sorted_models = []
        # 先按优先级列表找
        for kw in priority_keywords:
            for name in available_names:
                if kw in name and name not in sorted_models:
                    sorted_models.append(name)
        
        # 把剩下的加进去作为最后的备选
        for name in available_names:
            if name not in sorted_models:
                sorted_models.append(name)

        return sorted_models, "Success"

    except Exception as e:
        return [], str(e)

# --- 5. 增强版 API 调用：支持模型自动切换 ---
def smart_api_call(model_list, payload, api_key, status_box=None):
    """
    智能调用函数：
    1. 遍历模型列表。
    2. 如果遇到 429/500/503，自动切换下一个模型。
    3. 如果遇到 400 (Bad Request)，尝试降级策略（移除 Search 工具）。
    """
    last_error = None
    
    for i, model_name in enumerate(model_list):
        # 确保模型名称格式正确
        if not model_name.startswith("models/"): 
            full_model_name = f"models/{model_name}"
        else:
            full_model_name = model_name
            
        api_url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_name}:generateContent?key={api_key}"
        
        if status_box:
            status_box.write(f"🔄 正在尝试模型节点 ({i+1}/{len(model_list)}): `{model_name.replace('models/', '')}` ...")
        
        try:
            # 发起请求
            response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
            
            # --- 场景 A: 成功 ---
            if response.status_code == 200:
                return response
            
            # --- 场景 B: 400 Bad Request (通常是 Search 工具不兼容) ---
            elif response.status_code == 400:
                # 尝试移除 tools 再试一次当前模型
                if "tools" in payload:
                    if status_box: status_box.write("⚠️ 检测到工具兼容性问题，正在切换至纯文本分析模式...")
                    payload_no_tools = payload.copy()
                    del payload_no_tools["tools"]
                    response_retry = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload_no_tools)
                    if response_retry.status_code == 200:
                        return response_retry
                
                # 如果还是不行，记录错误继续下一个模型
                last_error = response
                continue

            # --- 场景 C: 429/503 (限流或服务不可用) ---
            elif response.status_code in [429, 503, 500]:
                if status_box: status_box.write(f"⏳ 模型 `{model_name}` 繁忙或配额耗尽，自动切换下一节点...")
                time.sleep(1) # 小睡一下给服务器喘息
                last_error = response
                continue
            
            # 其他错误
            else:
                last_error = response
                continue

        except Exception as e:
            if status_box: status_box.write(f"❌ 网络异常: {e}")
            continue

    # 如果所有模型都试过了还是失败
    return last_error

# --- 6. 辅助函数：解析 AI 返回的 JSON ---
def parse_json_response(text):
    """
    超级鲁棒的解析器 V3.5：
    1. 尝试直接解析。
    2. 尝试正则清理 Markdown。
    3. 暴力搜索最外层的 {} 或 []。
    4. 尝试修复单引号问题 (Python dict 格式)。
    """
    if not text: return None

    # 方法 1: 直接解析
    try:
        return json.loads(text)
    except:
        pass
    
    # 方法 2: 清理 Markdown 代码块
    try:
        clean_text = re.sub(r'```json\s*', '', text)
        clean_text = re.sub(r'```\s*$', '', clean_text)
        clean_text = clean_text.strip()
        return json.loads(clean_text)
    except:
        pass

    # 方法 3: 暴力寻找 JSON 结构
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

    # 方法 4: 终极尝试 - AST 解析 (处理 Python 风格的单引号字典)
    try:
        if start_obj != -1 and end != -1:
             # 有时候模型返回 {'key': 'value'} 而不是 {"key": "value"}
             # ast.literal_eval 可以安全地解析 Python 结构
             potential_dict = text[start : end+1]
             return ast.literal_eval(potential_dict)
    except:
        pass

    return None

# --- 新增：收藏功能函数 ---
def add_to_favorites(category, title, content_data):
    """
    category: 'Check' | 'Search' | 'Rewrite'
    title: 简短标题
    content_data: 完整数据 (JSON或文本)
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = {
        "id": f"{category}_{int(time.time()*1000)}",
        "category": category,
        "title": title,
        "content": content_data,
        "time": timestamp
    }
    st.session_state["favorites"].append(item)
    st.toast(f"✅ 已收藏到【我的收藏】: {title}", icon="⭐")

def delete_favorite(index):
    if 0 <= index < len(st.session_state["favorites"]):
        del st.session_state["favorites"][index]
        st.rerun()

# --- 7. 核心页面逻辑 ---
# 侧边栏
with st.sidebar:
    st.title("⚛️ Nuclear Hub")
    st.info(
        """
        **版本**: Pro Max v4.1 (Restore)
        
        **功能恢复与升级**：
        1. 完整恢复了深度指令 Prompt (V3.x)。
        2. 增加了收藏夹功能 (V4.0)。
        3. 保留了智能轮询与容错解析。
        """
    )
    st.caption("Powered by Google Gemini & Streamlit")

st.title("Nuclear Knowledge Hub")
st.caption("🚀 核科学事实核查、学术检索与专业改写平台")

# 创建四个独立的 Tabs
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
                    # --- 恢复完整的 Prompt ---
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
                                    "url": "来源链接"
                                }}
                            ]
                        }}
                    ]
                    """
                    
                    payload = {"contents": [{"parts": [{ "text": prompt_check }]}], "tools": [{"google_search": {}}]}
                    response = smart_api_call(model_list, payload, API_KEY, status_box)
                    
                    if response and response.status_code == 200:
                        raw_content = response.json().get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', "")
                        check_results = parse_json_response(raw_content)
                        status_box.update(label="分析完成", state="complete", expanded=False)
                        
                        st.session_state["check_result"] = {"data": check_results, "raw": raw_content, "query": user_text_check[:20]+"..."}
                    else:
                        st.error("请求失败，请重试")

        # 2. 显示逻辑
        if st.session_state.get("check_result"):
            res_data = st.session_state["check_result"].get("data")
            raw_text = st.session_state["check_result"].get("raw")
            
            col_act1, col_act2 = st.columns([1, 4])
            with col_act1:
                if st.button("❤️ 收藏报告", key="fav_btn_check"):
                    add_to_favorites("Check", st.session_state["check_result"]["query"], st.session_state["check_result"])
            st.divider()

            if res_data:
                for item in res_data:
                    status = item.get('status', '存疑')
                    if "错" in status:
                        border_color = "#ff4b4b"; icon = "❌"; title_color = "#ff8a80"
                    elif "疑" in status or "不一致" in status:
                        border_color = "#ffa726"; icon = "⚠️"; title_color = "#ffcc80"
                    else:
                        border_color = "#66bb6a"; icon = "✅"; title_color = "#a5d6a7"
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="check-card" style="border-left: 5px solid {border_color};">
                            <div style="margin-bottom: 12px;">
                                <span style="font-weight: bold; font-size: 1.3em; color: {title_color};">{icon} {status}</span>
                                <div style="color: #b0bec5; font-size: 0.9em; margin-top: 4px;">陈述：{item.get('claim', '')}</div>
                            </div>
                            <div style="margin-bottom: 15px; line-height: 1.6;">
                                <b>💡 专家分析：</b><br>{item.get('correction', '无详细分析')}
                            </div>
                        """, unsafe_allow_html=True)
                        
                        evidence_list = item.get('evidence_list', [])
                        if not evidence_list and 'evidence_quote' in item: evidence_list = [{'source_name': '权威数据', 'content': item['evidence_quote'], 'url': '#'}]
                        if evidence_list:
                            st.markdown('<div class="evidence-container">', unsafe_allow_html=True)
                            st.markdown('<div style="color: #555; margin-bottom: 8px; font-weight:bold;">🔍 权威数据/原文证据：</div>', unsafe_allow_html=True)
                            for ev in evidence_list:
                                st.markdown(f"""
                                <div class="quote-item"><span class="tag-pill">[{ev.get('source_name', '来源')}]</span>"{ev.get('content', '')}"<br>
                                <a href="{ev.get('url', '#')}" target="_blank" class="source-link" style="margin-top:4px; display:inline-block;">🔗 来源</a></div>
                                """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
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
                    # --- 恢复完整的 Prompt ---
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
                                "doi": "DOI或空字符串",
                                "url": "真实URL"
                            }}
                        ]
                    }}
                    """
                    
                    payload = {"contents": [{"parts": [{ "text": prompt_search }]}], "tools": [{"google_search": {}}]}
                    response = smart_api_call(model_list, payload, API_KEY, status_box_search)
                    
                    if response and response.status_code == 200:
                        raw_content = response.json().get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', "")
                        search_results = parse_json_response(raw_content)
                        status_box_search.update(label="检索完成", state="complete", expanded=False)
                        st.session_state["search_result"] = {"data": search_results, "raw": raw_content, "query": search_query}
                    else:
                        st.error("请求失败")
        
        if st.session_state.get("search_result"):
            s_res = st.session_state["search_result"].get("data")
            s_raw = st.session_state["search_result"].get("raw")
            
            col_act_s1, col_act_s2 = st.columns([1, 4])
            with col_act_s1:
                if st.button("❤️ 收藏结果", key="fav_btn_search"):
                    add_to_favorites("Search", st.session_state["search_result"]["query"], st.session_state["search_result"])
            st.divider()

            if s_res:
                papers = s_res.get('papers', []) if isinstance(s_res, dict) else s_res
                overview = s_res.get('overview', "") if isinstance(s_res, dict) else ""
                
                if overview:
                    st.markdown(f"""<div class="overview-card"><div style="font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">🧪 学术综述 (Overview)</div><div style="line-height: 1.6;">{overview}</div></div>""", unsafe_allow_html=True)

                if papers:
                    st.success(f"检索到 {len(papers)} 篇相关文献或报道")
                    for item in papers:
                        with st.container():
                            st.markdown(f"""
                            <div class="research-card">
                                <div style="font-size: 1.2em; font-weight: bold; color: #63b3ed; margin-bottom: 5px;">📄 {item.get('title', '无标题')}</div>
                                <div style="font-size: 0.9em; color: #a0aec0; margin-bottom: 15px;">{item.get('authors', 'N/A')} | {item.get('publication', 'N/A')}, {item.get('year', 'N/A')}</div>
                                <div style="border-top: 1px solid #4a5568; margin-bottom: 10px;"></div>
                                <div style="line-height: 1.6; color: #cbd5e0; font-family: 'Noto Serif SC', serif;">{item.get('summary', '暂无摘要')}</div>
                            """, unsafe_allow_html=True)
                            col_l1, col_l2, col_l3 = st.columns([1, 1, 4])
                            st.markdown(f'<a href="{item.get("url", "#")}" target="_blank" class="source-link">🔗 原文</a>', unsafe_allow_html=True)
                            if item.get('doi'): st.markdown(f'<a href="https://x.sci-hub.org.cn/{item.get("doi")}" target="_blank" class="source-link scihub-btn">🔓 Sci-Hub</a>', unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)
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
                    # --- 恢复完整的 Prompt ---
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
                    
                    payload = {"contents": [{"parts": [{ "text": prompt_rewrite }]}]}
                    response = smart_api_call(model_list, payload, API_KEY, status_box_rewrite)
                    
                    if response and response.status_code == 200:
                        full_text = response.json().get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', "")
                        status_box_rewrite.update(label="润色完成", state="complete", expanded=False)
                        
                        rewrite_c = full_text
                        trans_c = ""
                        if "[REWRITE]" in full_text and "[TRANSLATION]" in full_text:
                            parts = full_text.split("[TRANSLATION]")
                            rewrite_c = parts[0].replace("[REWRITE]", "").strip()
                            trans_c = parts[1].strip()
                        
                        st.session_state["rewrite_result"] = {
                            "rewrite": rewrite_c, 
                            "translation": trans_c, 
                            "draft": user_text_rewrite
                        }
                    else:
                        st.error("请求失败")

        if st.session_state.get("rewrite_result"):
            res = st.session_state["rewrite_result"]
            
            col_act_r1, col_act_r2 = st.columns([1, 4])
            with col_act_r1:
                if st.button("❤️ 收藏改写", key="fav_btn_rewrite"):
                    title_preview = res["rewrite"][:20].replace("\n", " ") + "..."
                    add_to_favorites("Rewrite", title_preview, res)
            st.divider()

            trans_html = f"""<div class="translation-section"><div style="margin-bottom: 8px; font-weight: bold;">🌐 Translation:</div>{res['translation'].replace(chr(10), '<br>')}</div>""" if res['translation'] else ""
            st.markdown(f"""
            <div class="rewrite-card">
                <div style="margin-bottom: 10px; font-weight: bold; color: #81e6d9;">🖋️ Revised Text:</div>
                {res['rewrite'].replace(chr(10), '<br>')}
                {trans_html}
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 模块四：我的收藏 (Favorites)
# ==========================================
with tab4:
    st.markdown("### ⭐ 我的收藏夹")
    
    if not st.session_state["favorites"]:
        st.info("暂无收藏内容。请在其他板块点击 ❤️ 收藏按钮。")
    else:
        for index, item in enumerate(reversed(st.session_state["favorites"])):
            original_index = len(st.session_state["favorites"]) - 1 - index
            
            with st.expander(f"[{item['category']}] {item['title']} - {item['time']}", expanded=False):
                col_del, col_content = st.columns([1, 6])
                with col_del:
                    if st.button("🗑️ 删除", key=f"del_{item['id']}"):
                        delete_favorite(original_index)
                
                with col_content:
                    content = item['content']
                    if item['category'] == 'Rewrite':
                        st.caption("**原始草稿:**")
                        st.text(content.get('draft', ''))
                        st.caption("**改写结果:**")
                        st.markdown(content.get('rewrite', ''))
                        if content.get('translation'):
                            st.divider()
                            st.caption("**翻译:**")
                            st.markdown(content.get('translation', ''))
                            
                    elif item['category'] == 'Check':
                        st.caption("**核查详情:**")
                        data = content.get('data')
                        if data and isinstance(data, list):
                            for claim_item in data:
                                st.markdown(f"> **陈述**: {claim_item.get('claim')}")
                                st.markdown(f"> **分析**: {claim_item.get('correction')}")
                                st.divider()
                        else:
                            st.markdown(content.get('raw', '无法解析的内容'))
                            
                    elif item['category'] == 'Search':
                        st.caption("**检索结果:**")
                        data = content.get('data')
                        if data and isinstance(data, dict):
                            st.markdown(f"**综述**: {data.get('overview', '')}")
                            st.markdown("**文献列表**:")
                            for p in data.get('papers', []):
                                st.markdown(f"- [{p.get('title')}]({p.get('url')})")
                        else:
                            st.markdown(content.get('raw', '无法解析的内容'))
