import streamlit as st
import google.generativeai as genai
import os
import time # 用于模拟一些延迟或进度条，实际API调用不需要

# --- Streamlit 页面配置 ---
st.set_page_config(
    page_title="🎵 Gemini 音频智能助手",
    page_icon="✨",
    layout="wide", # 宽布局
    initial_sidebar_state="expanded" # 侧边栏默认展开
)

# --- 样式调整 (可选，但能让界面更美观) ---
st.markdown("""
    <style>
    .reportview-container .main .block-container{
        padding-top: 2rem;
        padding-right: 2rem;
        padding-left: 2rem;
        padding-bottom: 2rem;
    }
    .css-1d391kg { /* Streamlit 侧边栏的类名，用于调整宽度 */
        width: 300px;
    }
    .stButton>button {
        background-color: #4CAF50; /* 按钮背景色 */
        color: white; /* 按钮文字颜色 */
        font-weight: bold;
        border-radius: 8px; /* 圆角 */
        padding: 10px 20px;
        font-size: 16px;
    }
    .stButton>button:hover {
        background-color: #45a049; /* 鼠标悬停时的背景色 */
    }
    .stAudio {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)


st.title("🎵 Gemini 音频智能助手")
st.markdown("通过 Google Gemini 多模态模型，轻松分析、理解您的音频内容。")
st.divider() # 分割线，让布局更清晰

api_key = os.getenv("GOOGLE_API_KEY") # <-- 直接从环境变量获取

# API Key 提示与配置引导
if not api_key:
    st.error("⚠️ **Google API Key 未设置！** 请在继续之前配置。", icon="🔑")
    st.info("""
    **配置方式：**
    - **部署到 Zeabur/Streamlit Cloud**: 在项目根目录下的 `.streamlit/secrets.toml` 文件中添加 `GOOGLE_API_KEY = "your_api_key_here"`
    - **本地运行**: 设置环境变量 `export GOOGLE_API_KEY="your_api_key_here"`
    """)
    st.stop() # 如果没有 API Key，停止应用运行

try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ 配置 Google GenAI 失败：{e}", icon="⛔")
    st.stop()

# --- 用户界面 (侧边栏) ---
st.sidebar.header("⚙️ 应用设置")

# 模型选择
model_options = {
    "Gemini 2.5 Flash (快速)": "gemini-2.5-flash",
    "Gemini 2.5 Pro (强大)": "gemini-2.5-pro",
    # 可以在这里添加更多模型选项
}
selected_model_name = st.sidebar.selectbox(
    "选择 Gemini 模型:",
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
    type=["mp3", "wav", "flac", "ogg", "m4a"], # 支持常见的音频格式
    help="支持的音频格式包括 MP3、WAV、FLAC、OGG、M4A 等。文件大小建议在 10MB 以下以获得更快的响应，Google API 对音频时长和大小有一定限制。"
)

st.sidebar.divider() # 分割线

# Prompt 输入
st.sidebar.subheader("📝 输入您的 Prompt")
default_prompt = "请详细描述这个音频剪辑的内容，识别其中的任何声音、音乐或语音。总结其主要信息。如果包含语音，请尝试转录关键信息。"
user_prompt = st.sidebar.text_area(
    "对模型说些什么？",
    value=default_prompt,
    height=180,
    help="输入您想让 Gemini 模型对音频执行的任务或提问。例如：'分析这段音乐的风格和情绪'、'转录这段对话的主要内容'等。"
)

st.sidebar.markdown("---") # 再一个分割线
analyze_button = st.sidebar.button("🚀 开始分析", use_container_width=True) # 按钮填满侧边栏宽度

# --- 主内容区域 ---
st.header("✨ 分析结果")

# 创建占位符，用于动态显示状态和结果
status_message_placeholder = st.empty()
uploaded_audio_player_placeholder = st.empty()
analysis_result_placeholder = st.empty()

# --- 处理逻辑 ---
if analyze_button:
    if uploaded_file is None:
        status_message_placeholder.warning("⚠️ 请先上传一个音频文件！", icon="⬆️")
    else:
        # 清除之前的消息和结果
        status_message_placeholder.empty()
        uploaded_audio_player_placeholder.empty()
        analysis_result_placeholder.empty()

        status_message_placeholder.info("⏳ 准备就绪，正在开始分析...", icon="🔄")

        file_to_analyze = None # 用于 finally 块确保文件被删除
        try:
            # 1. 显示已上传的音频（可选）
            with uploaded_audio_player_placeholder.container():
                st.subheader("▶️ 已上传音频预览:")
                st.audio(uploaded_file, format=uploaded_file.type, start_time=0)
                st.markdown(f"**文件名称:** `{uploaded_file.name}` | **文件大小:** `{round(uploaded_file.size / (1024 * 1024), 2)} MB`")
                st.divider()


            # 2. 将文件上传到 Google GenAI 服务
            with status_message_placeholder.status("正在上传音频到 Google GenAI 服务...", expanded=True) as status_box:
                file_to_analyze = genai.upload_file(
                    uploaded_file.getvalue(),
                    mime_type=uploaded_file.type # Streamlit 自动检测 MIME 类型
                )
                status_box.update(label=f"文件上传成功！文件 ID: `{file_to_analyze.name}`", state="complete", expanded=False)
                # 可以选择在这里显示文件ID，但为了界面简洁，直接成功即可

            # 3. 调用 Gemini 模型生成内容
            with status_message_placeholder.status(f"正在使用 `{selected_model_name}` 模型生成内容...", expanded=True) as status_box:
                model = genai.GenerativeModel(selected_model_id)
                response = model.generate_content(
                    contents=[user_prompt, file_to_analyze]
                )
                status_box.update(label="模型响应已获取！", state="complete", expanded=False)

            # 4. 显示模型回复
            analysis_result_placeholder.success("✅ 分析完成！", icon="🎉")
            analysis_result_placeholder.markdown(f"### 🤖 Gemini 的分析结果 ({selected_model_name}):")
            analysis_result_placeholder.markdown(response.text)


        except genai.types.BlockedPromptException as e:
            status_message_placeholder.error(f"⚠️ 您的请求被模型安全设置阻止了。请尝试修改 Prompt 或音频内容。错误详情: {e}", icon="🚫")
            analysis_result_placeholder.empty() # 清除可能遗留的成功信息
        except Exception as e:
            status_message_placeholder.error(f"❌ 分析过程中发生错误：{e}", icon="⛔")
            status_message_placeholder.warning("请检查您的 API Key 是否有效、网络连接是否正常，以及上传的音频文件是否有效且符合模型处理要求（例如，音频内容是否清晰可识别，文件大小是否过大）。", icon="💡")
            analysis_result_placeholder.empty() # 清除可能遗留的成功信息
        finally:
            # 5. 无论成功或失败，都尝试删除上传到 Google 服务的文件以节省资源和存储
            if file_to_analyze:
                try:
                    with status_message_placeholder.status(f"正在删除 Google GenAI 服务上的临时文件 `{file_to_analyze.name}`...", expanded=True) as status_box:
                        genai.delete_file(file_to_analyze.name)
                        status_box.update(label="临时文件已从 GenAI 服务删除。", state="complete", expanded=False)
                except Exception as e:
                    status_message_placeholder.error(f"清理临时文件失败：{e}", icon="🗑️")