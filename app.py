import streamlit as st
import google.generativeai as genai
from google.generativeai import protos # <-- 导入 protos 模块，用于构建内嵌二进制数据
import os
import time # 用于模拟一些延迟或进度条，实际API调用不直接使用

# --- Streamlit 页面配置 ---
st.set_page_config(
    page_title="🎵 Gemini 音频智能助手",
    page_icon="✨",
    layout="wide", # 使用宽布局，充分利用屏幕空间
    initial_sidebar_state="expanded" # 侧边栏默认展开
)

# --- 顶部标题和描述 ---
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>🎵 Gemini 音频智能助手 ✨</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: grey;'>利用 Google Gemini 多模态模型，深度分析和理解您的音频内容。</p>", unsafe_allow_html=True)
st.divider() # 一条漂亮的分割线

# --- Google API Key 配置 ---
# 直接从环境变量获取 API Key (推荐用于部署，如 Zeabur)
api_key = os.getenv("GOOGLE_API_KEY")

# API Key 提示与配置引导
if not api_key:
    st.warning("⚠️ **Google API Key 未设置！** 请在继续之前配置。", icon="🔑")
    st.info("""
    **配置方式：**
    - **部署到 Zeabur**: 在 Zeabur 控制台的环境变量中添加 `GOOGLE_API_KEY = "your_api_key_here"`
    - **本地运行**: 在终端中设置环境变量 `export GOOGLE_API_KEY="your_api_key_here"`
    """)
    st.stop() # 如果没有 API Key，停止应用运行

# 配置 Google Generative AI 客户端
try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ 配置 Google GenAI 客户端失败：{e}", icon="⛔")
    st.exception(e) # 显示详细的异常信息，方便调试
    st.stop()

# --- 侧边栏：操作面板 ---
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
    index=0, # 默认选中第一个 Flash 模型
    help="Gemini 2.5 Flash 速度更快、成本更低，适合快速概括；Gemini 2.5 Pro 功能更强大，理解更深入，但可能响应稍慢且成本更高。"
)
selected_model_id = model_options[selected_model_name]

st.sidebar.divider() # 分割线

# 音频文件上传
st.sidebar.subheader("📤 上传音频文件")
uploaded_file = st.sidebar.file_uploader(
    "选择一个音频文件 (.mp3, .wav, .flac 等)",
    type=["mp3", "wav", "flac", "ogg", "m4a"], # 支持常见音频格式
    help="支持的音频格式包括 MP3、WAV、FLAC、OGG、M4A 等。请注意，直接内嵌音频到请求中通常适合**较短**的音频片段（建议文件大小在几MB以内，例如1-4分钟），过大文件可能导致请求失败或超时。"
)

st.sidebar.divider() # 分割线

# Prompt 输入
st.sidebar.subheader("📝 定义您的分析任务")
default_prompt = "请详细描述这个音频剪辑的内容，识别其中的任何声音、音乐或语音。总结其主要信息。如果包含语音，请尝试转录关键信息。"
user_prompt = st.sidebar.text_area(
    "对模型说些什么？",
    value=default_prompt,
    height=300, # 增大高度，提供更好的输入体验
    help="输入您想让 Gemini 模型对音频执行的任务或提问。例如：'分析这段音乐的风格和情绪'、'转录这段对话的主要内容'等。"
)

st.sidebar.markdown("---") # 再一个分割线
analyze_button = st.sidebar.button("🚀 开始分析音频", use_container_width=True) # 按钮填满侧边栏宽度

# --- 主内容区域 ---
# 使用 st.container 和 st.expander 来组织输出，使界面更整洁
main_output_container = st.container()

with main_output_container:
    # 占位符，用于动态显示状态信息（如上传中、分析中、成功、错误）
    status_message_area = st.empty()
    # Expander 用于折叠和展开音频预览区域
    uploaded_audio_preview_expander = st.expander("▶️ 点击预览已上传音频", expanded=False)
    # Expander 用于折叠和展开 Gemini 分析结果区域
    analysis_result_expander = st.expander("✨ Gemini 分析结果", expanded=False)

# --- 处理逻辑 ---
if analyze_button:
    if uploaded_file is None:
        status_message_area.warning("⚠️ 请先上传一个音频文件！", icon="⬆️")
        # 清除所有展开的区域，确保界面状态一致
        uploaded_audio_preview_expander.empty()
        analysis_result_expander.empty()
    else:
        # 清除之前的消息和结果，准备显示新的分析
        status_message_area.empty()
        uploaded_audio_preview_expander.empty()
        analysis_result_expander.empty()
        
        # 强制展开预览和结果区域，便于用户查看过程和最终结果
        uploaded_audio_preview_expander.expanded = True
        analysis_result_expander.expanded = True

        status_message_area.info("⏳ 正在准备分析，请稍候...", icon="🔄")

        try:
            # 1. 显示已上传的音频预览
            with uploaded_audio_preview_expander: # 在 Expander 内部显示内容
                st.subheader("已上传音频:")
                st.audio(uploaded_file, format=uploaded_file.type, start_time=0)
                # 使用两列布局显示文件信息，美观且节省空间
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**文件名称:** `{uploaded_file.name}`")
                with col2:
                    st.markdown(f"**文件大小:** `{round(uploaded_file.size / (1024 * 1024), 2)} MB`")
                st.markdown("---") # 内部小分割线


            # 2. 获取音频字节流并创建 protos.Part 对象，用于内嵌传输
            with status_message_area.status("正在准备音频内容...", expanded=True) as status_box:
                audio_bytes = uploaded_file.getvalue() # 获取上传文件的原始字节流
                
                # 使用 google.generativeai.protos 显式构建 Part 对象
                # 这是将二进制数据（如音频）作为内联内容发送给 Gemini API 的正确方式
                audio_part = protos.Part(
                    inline_data=protos.Blob(
                        data=audio_bytes,
                        mime_type=uploaded_file.type # 使用 Streamlit 自动检测到的 MIME 类型
                    )
                )
                status_box.update(label="音频内容已准备就绪！", state="complete", expanded=False)


            # 3. 调用 Gemini 模型生成内容
            with status_message_area.status(f"正在使用 `{selected_model_name}` 模型分析内容...", expanded=True) as status_box:
                model = genai.GenerativeModel(selected_model_id)
                response = model.generate_content(
                    contents=[user_prompt, audio_part] # 传入用户 Prompt 和构建好的音频 Part 对象
                )
                status_box.update(label="模型响应已获取！", state="complete", expanded=False)


            # 4. 显示模型回复
            status_message_area.success("✅ 分析完成！请查看下方结果。", icon="🎉")
            with analysis_result_expander: # 在 Expander 内部显示结果
                st.markdown(f"### 🤖 Gemini 的详细分析结果 ({selected_model_name}):")
                st.markdown(response.text) # 显示模型的文本回复


        except genai.types.BlockedPromptException as e:
            # 捕获模型安全设置引发的异常
            status_message_area.error(f"⚠️ 您的请求被模型安全设置阻止了。请尝试修改 Prompt 或音频内容。", icon="🚫")
            st.exception(e) # 显示详细的异常信息，帮助调试
            uploaded_audio_preview_expander.empty()
            analysis_result_expander.empty()
        except Exception as e:
            # 捕获所有其他通用异常
            status_message_area.error(f"❌ 分析过程中发生意外错误。", icon="⛔")
            status_message_area.warning("💡 请检查您的 API Key 是否有效、网络连接是否正常，以及上传的音频文件是否有效且符合模型处理要求（例如，音频内容是否清晰可识别，文件大小是否过大，时长是否超过10分钟）。", icon="🔍")
            st.exception(e) # 显示详细的异常信息，非常重要用于调试部署问题
            uploaded_audio_preview_expander.empty()
            analysis_result_expander.empty()
        finally:
            # 使用内嵌音频方式，无需清理 Google 服务上的临时文件，因此此 finally 块现在是空的
            pass


# --- 页脚 (可选) ---
st.markdown("---")
st.markdown("""
    <p style='text-align: center; color: grey; font-size: 0.9em;'>
        由 Streamlit & Google Gemini API 驱动 🚀 <br>
        如果您喜欢这个应用，请分享给您的朋友！
    </p>
""", unsafe_allow_html=True)