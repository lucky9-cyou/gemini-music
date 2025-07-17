import streamlit as st
import google.generativeai as genai
import os
import time
import asyncio
import threading

# --- Streamlit 页面配置 ---
st.set_page_config(
    page_title="🎵 Gemini 音频智能助手 - 并发版",
    page_icon="✨",
    layout="wide", # 宽布局
    initial_sidebar_state="expanded" # 侧边栏默认展开
)

# --- 顶部标题和描述 ---
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>🎵 Gemini 音频智能助手 ✨ (并发模式)</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: grey;'>利用 Google Gemini 多模态模型，深度分析和理解您的音频内容，并可同时处理多个请求。</p>", unsafe_allow_html=True)
st.divider() # 分割线，让布局更清晰

# --- Google API Key 配置 ---
api_key = os.getenv("GOOGLE_API_KEY") # 直接从环境变量获取

# API Key 提示与配置引导
if not api_key:
    st.warning("⚠️ **Google API Key 未设置！** 请在继续之前配置。", icon="🔑")
    st.info("""
    **配置方式：**
    - **部署到 Zeabur**: 在 Zeabur 控制台的环境变量中添加 `GOOGLE_API_KEY = "your_api_key_here"`
    - **本地运行**: 设置环境变量 `export GOOGLE_API_KEY="your_api_key_here"`
    """)
    st.stop() # 如果没有 API Key，停止应用运行

try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ 配置 Google GenAI 失败：{e}", icon="⛔")
    st.stop()

# --- Streamlit Session State 初始化 ---
if 'tasks' not in st.session_state:
    st.session_state.tasks = [] # 存储所有并发任务的状态和结果
if 'running_concurrently' not in st.session_state:
    st.session_state.running_concurrently = False # 标记是否有并发任务正在运行

# --- 定义异步任务函数 ---
# 这是一个在后台异步执行的单个 Gemini API 调用
async def async_gemini_analysis_task(task_index, prompt, audio_bytes, mime_type, model_id):
    """
    异步执行单个 Gemini 音频分析任务。
    更新 session_state 并在每次状态变化后调用 st.rerun()。
    """
    try:
        # 更新任务状态为“进行中”
        st.session_state.tasks[task_index]['status'] = '进行中'
        st.session_state.tasks[task_index]['message'] = f"正在用 {model_id} 模型分析..."
        st.rerun() # 通知 Streamlit 刷新 UI

        model = genai.GenerativeModel(model_id)
        
        # 实际的 Gemini API 调用
        # 注意：genai.generate_content 本身不是 async，但在 asyncio 线程中运行没问题
        response = model.generate_content(
            contents=[prompt, (audio_bytes, mime_type)]
        )

        # 更新任务状态为“完成”
        st.session_state.tasks[task_index]['status'] = '完成'
        st.session_state.tasks[task_index]['result'] = response.text
        st.session_state.tasks[task_index]['message'] = '分析成功！'
        st.rerun() # 通知 Streamlit 刷新 UI

    except genai.types.BlockedPromptException as e:
        st.session_state.tasks[task_index]['status'] = '被阻止'
        st.session_state.tasks[task_index]['message'] = f"请求被模型安全设置阻止: {e}"
        st.session_state.tasks[task_index]['error_details'] = str(e)
        st.rerun()
    except Exception as e:
        st.session_state.tasks[task_index]['status'] = '失败'
        st.session_state.tasks[task_index]['message'] = f"分析失败: {e}"
        st.session_state.tasks[task_index]['error_details'] = str(e)
        st.rerun()


# --- 后台线程函数 ---
def run_concurrent_analysis_thread(num_concurrent_requests, user_prompt, uploaded_file_bytes, uploaded_file_type, model_id):
    """
    在单独的线程中运行 asyncio 事件循环，执行并发任务。
    """
    st.session_state.running_concurrently = True
    st.session_state.tasks = [] # 重置任务列表

    # 初始化所有任务的状态
    for i in range(num_concurrent_requests):
        st.session_state.tasks.append({
            'id': i + 1,
            'status': '待处理',
            'message': '等待开始...',
            'result': None,
            'error_details': None
        })
    st.rerun() # 立即刷新 UI，显示所有待处理任务

    # 创建一个 asyncio 事件循环并在其中运行并发任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tasks_to_run = [
        async_gemini_analysis_task(
            i,
            user_prompt,
            uploaded_file_bytes,
            uploaded_file_type,
            model_id
        )
        for i in range(num_concurrent_requests)
    ]

    # 等待所有并发任务完成
    loop.run_until_complete(asyncio.gather(*tasks_to_run))
    loop.close()

    st.session_state.running_concurrently = False
    st.rerun() # 所有任务完成后，再次刷新 UI


# --- 用户界面 (侧边栏) ---
st.sidebar.header("⚙️ 操作面板")

# 模型选择
st.sidebar.subheader("🤖 选择 Gemini 模型")
model_options = {
    "Gemini 2.5 Flash (快速高效)": "gemini-2.5-flash",
    "Gemini 2.5 Pro (深度理解)": "gemini-2.5-pro",
}
selected_model_name = st.sidebar.selectbox(
    "模型版本:",
    options=list(model_options.keys()),
    index=0, # 默认选中第一个
    help="Gemini 2.5 Flash 速度更快、成本更低，适合快速概括；Gemini 2.5 Pro 功能更强大，理解更深入，但可能响应稍慢且成本更高。"
)
selected_model_id = model_options[selected_model_name]

st.sidebar.divider() # 分割线

# 音频文件上传
st.sidebar.subheader("📤 上传音频文件")
uploaded_file = st.sidebar.file_uploader(
    "选择一个音频文件 (.mp3, .wav, .flac 等)",
    type=["mp3", "wav", "flac", "ogg", "m4a"],
    help="支持的音频格式包括 MP3、WAV、FLAC、OGG、M4A 等。请注意，直接内嵌音频到请求中通常适合**较短**的音频片段（建议几MB以内，例如1-4分钟），过大文件可能导致请求失败。"
)

st.sidebar.divider() # 分割线

# Prompt 输入
st.sidebar.subheader("📝 定义您的分析任务")
default_prompt = "请详细描述这个音频剪辑的内容，识别其中的任何声音、音乐或语音。总结其主要信息。如果包含语音，请尝试转录关键信息。"
user_prompt = st.sidebar.text_area(
    "对模型说些什么？",
    value=default_prompt,
    height=300, # 增大高度到 300
    help="输入您想让 Gemini 模型对音频执行的任务或提问。例如：'分析这段音乐的风格和情绪'、'转录这段对话的主要内容'等。"
)

st.sidebar.divider()

# 并发请求数量设置
num_concurrent_requests = st.sidebar.slider(
    "并发请求数量:",
    min_value=1,
    max_value=10, # 最大设置为 10 个并发
    value=5, # 默认 5 个
    help="同时向 Gemini API 发送的请求数量。过高的并发数可能触发 API 速率限制。"
)

st.sidebar.markdown("---")

# 按钮：单次分析 和 并发分析
col_btn1, col_btn2 = st.sidebar.columns(2)

with col_btn1:
    single_analyze_button = st.button("🚀 单次分析", use_container_width=True, disabled=st.session_state.running_concurrently)
with col_btn2:
    concurrent_analyze_button = st.button("⚡ 并发分析", use_container_width=True, disabled=st.session_state.running_concurrently)

# --- 主内容区域 ---
main_output_container = st.container()

with main_output_container:
    status_message_area = st.empty()
    uploaded_audio_preview_expander = st.expander("▶️ 点击预览已上传音频", expanded=False)
    
    if st.session_state.running_concurrently:
        st.info("⚡️ 并发任务正在后台运行，请等待...")
        # 遍历显示所有并发任务的实时状态
        st.subheader(f"📊 并发任务 ({len(st.session_state.tasks)}/{num_concurrent_requests}) 状态:")
        for task in st.session_state.tasks:
            status_emoji = {
                '待处理': '⚪',
                '进行中': '⏳',
                '完成': '✅',
                '失败': '❌',
                '被阻止': '🚫'
            }.get(task['status'], '❓')
            
            with st.status(f"任务 {task['id']}: {status_emoji} {task['message']}", expanded=(task['status'] in ['失败', '被阻止'])) as task_status_container:
                if task['result']:
                    st.markdown("**分析结果:**")
                    st.markdown(task['result'])
                if task['error_details']:
                    st.error(f"**错误详情:**\n```\n{task['error_details']}\n```")
            st.markdown("---") # 每个任务之间加个分隔线

    else: # 如果没有并发任务正在运行，显示单个任务的结果
        analysis_result_expander = st.expander("✨ Gemini 分析结果", expanded=False)


# --- 处理逻辑 (单次分析) ---
if single_analyze_button and not st.session_state.running_concurrently:
    if uploaded_file is None:
        status_message_area.warning("⚠️ 请先上传一个音频文件！", icon="⬆️")
        uploaded_audio_preview_expander.empty()
        analysis_result_expander.empty()
    else:
        status_message_area.empty()
        uploaded_audio_preview_expander.empty()
        analysis_result_expander.empty()
        
        uploaded_audio_preview_expander.expanded = True
        analysis_result_expander.expanded = True

        status_message_area.info("⏳ 正在准备分析，请稍候...", icon="🔄")

        try:
            with uploaded_audio_preview_expander:
                st.subheader("已上传音频:")
                st.audio(uploaded_file, format=uploaded_file.type, start_time=0)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**文件名称:** `{uploaded_file.name}`")
                with col2:
                    st.markdown(f"**文件大小:** `{round(uploaded_file.size / (1024 * 1024), 2)} MB`")
                st.markdown("---")


            with status_message_area.status("正在准备音频内容...", expanded=True) as status_box:
                audio_bytes = uploaded_file.getvalue()
                status_box.update(label="音频内容已准备就绪！", state="complete", expanded=False)


            with status_message_area.status(f"正在使用 `{selected_model_name}` 模型分析内容...", expanded=True) as status_box:
                model = genai.GenerativeModel(selected_model_id)
                response = model.generate_content(
                    contents=[user_prompt, (audio_bytes, uploaded_file.type)]
                )
                status_box.update(label="模型响应已获取！", state="complete", expanded=False)


            status_message_area.success("✅ 分析完成！请查看下方结果。", icon="🎉")
            with analysis_result_expander:
                st.markdown(f"### 🤖 Gemini 的详细分析结果 ({selected_model_name}):")
                st.markdown(response.text)


        except genai.types.BlockedPromptException as e:
            status_message_area.error(f"⚠️ 您的请求被模型安全设置阻止了。请尝试修改 Prompt 或音频内容。", icon="🚫")
            st.exception(e)
            uploaded_audio_preview_expander.empty()
            analysis_result_expander.empty()
        except Exception as e:
            status_message_area.error(f"❌ 分析过程中发生意外错误。", icon="⛔")
            status_message_area.warning("💡 请检查您的 API Key 是否有效、网络连接是否正常，以及上传的音频文件是否有效且符合模型处理要求（例如，音频内容是否清晰可识别，文件大小是否过大，时长是否超过10分钟）。", icon="🔍")
            st.exception(e)
            uploaded_audio_preview_expander.empty()
            analysis_result_expander.empty()
        finally:
            pass


# --- 处理逻辑 (并发分析) ---
if concurrent_analyze_button and not st.session_state.running_concurrently:
    if uploaded_file is None:
        status_message_area.warning("⚠️ 请先上传一个音频文件！", icon="⬆️")
    else:
        # 获取上传文件的字节流和MIME类型，用于传递给并发任务
        uploaded_file_bytes = uploaded_file.getvalue()
        uploaded_file_type = uploaded_file.type

        status_message_area.info(f"⚡️ 正在启动 {num_concurrent_requests} 个并发分析任务...", icon="🚀")
        
        # 启动一个新线程来运行并发分析
        thread = threading.Thread(
            target=run_concurrent_analysis_thread,
            args=(num_concurrent_requests, user_prompt, uploaded_file_bytes, uploaded_file_type, selected_model_id)
        )
        thread.start()
        # Streamlit 脚本会立即重新运行并显示初始任务状态


# --- 页脚 (可选) ---
st.markdown("---")
st.markdown("""
    <p style='text-align: center; color: grey; font-size: 0.9em;'>
        由 Streamlit & Google Gemini API 驱动 🚀 <br>
        如果您喜欢这个应用，请分享给您的朋友！
    </p>
""", unsafe_allow_html=True)