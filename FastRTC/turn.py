from gradio_webrtc import get_hf_turn_credentials, WebRTC


# Pass a valid access token for your Hugging Face account
# or set the HF_TOKEN environment variable 
credentials = get_hf_turn_credentials(token=None)

with gr.Blcocks() as demo:
    webrtc = WebRTC(rtc_configuration=credentials)
    ...

demo.launch()