# import os
# import re
# from marker.convert import convert_single_pdf
# from marker.logger import configure_logging
# from marker.models import load_all_models
# from marker.output import save_markdown



# fname = 'RIT.pdf'
# model_lst = load_all_models()
# full_text, images, out_meta = convert_single_pdf(fname, model_lst)

# # filtered_text = re.sub(r'!\[\d+_image_\d+\.png\]\(\d+_image_\d+\.png\)', '', full_text)
# #     # Assume tables are identifiable as structured text within `full_text`
# # text_sections = re.split(r'\n\n+', filtered_text)
# # full_text_str = "\n\n".join(text_sections)
# # fname = os.path.basename(fname)
# subfolder_path = save_markdown('marker-output', fname, full_text, images, out_meta)
# print(subfolder_path)

# print(f"Saved markdown to the {subfolder_path} folder")

# # from marker.converters.pdf import PdfConverter
# # from marker.models import create_model_dict
# # from marker.output import text_from_rendered
# # from marker.output import save_output

# # converter = PdfConverter(
# #     artifact_dict=create_model_dict(),
# # )
# # rendered = converter("RIT.pdf")
# # #text, _, images = text_from_rendered(rendered)
# # output_dir = "marker-output"
# # fname_base = "RIT"
# # save_output(rendered, output_dir, fname_base)

# # from marker.converters.pdf import PdfConverter
# # from marker.models import create_model_dict
# # from marker.output import text_from_rendered

# # converter = PdfConverter(
# #     artifact_dict=create_model_dict(),
# # )
# # rendered = converter("RIT.pdf")
# # text, _, images = text_from_rendered(rendered)
# # print(text)

# import requests

# # Define the API endpoint
# url = "https://llmwhisperer-api.us-central.unstract.com/api/v2/whisper?mode=form&output_mode=layout_preserving"

# # API Key
# api_key = "SnVHC0BVy3OtvLbnS7Xtvid4VCQ6tv5EZAu9WWhF4_g"

# # Path to the PDF file
# pdf_file_path = "RIT.pdf"

# # Headers
# headers = {
#     "Content-Type": "application/octet-stream",
#     "unstract-key": api_key
# }

# # Read the file and make the request
# with open(pdf_file_path, "rb") as file:
#     response = requests.post(url, headers=headers, data=file)

# # Print the response
# print(response.status_code)
# print(response.json())
# print(response.text)
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# import requests
# import os
# # Define the API endpoint
# whisper_hash = "ba1fbd83|cb5bf819d63a1a8fb325cee26b307c8b"  # Replace with your actual hash
# url = f"https://llmwhisperer-api.us-central.unstract.com/api/v2/whisper-retrieve?whisper_hash={whisper_hash}"

# # API Key
# api_key = "SnVHC0BVy3OtvLbnS7Xtvid4VCQ6tv5EZAu9WWhF4_g"

# # Headers
# headers = {
#     "unstract-key": api_key
# }

# # Make the GET request
# response = requests.get(url, headers=headers)
# data = response.json()
# result_text = data.get("result_text", "")

# # Define output file path
# output_dir = "unstarct_output"
# os.makedirs(output_dir, exist_ok=True)  # Create directory if it doesn't exist
# output_md = os.path.join(output_dir, "extracted_text.md")

# # Write to .md file
# with open(output_md, "w", encoding="utf-8") as file:
#     file.write(result_text)

# # Print the response
# print(response.status_code)
# #print(response.json())  # Assuming the response is in JSON format
# -----------------------------------------------------------------------------------------------------------------------------------------------------------

import pymupdf4llm

md_text = pymupdf4llm.to_markdown("1222-Nines.pdf")

import pathlib
pathlib.Path("pymupdf4llm_1222-Nines.md").write_bytes(md_text.encode())
print("Markdown saved to output.md")