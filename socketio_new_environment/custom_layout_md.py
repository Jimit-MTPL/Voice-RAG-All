import os

# Step 1: Read content from an existing Markdown file
def read_markdown(input_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        full_text = file.read()
    return full_text

# Step 2: Perform operations on the content (Modify this part as needed)
def process_markdown(content):
    # Example operation: Replace multiple newlines with a single newline
    import re
    text_sections = re.split(r'\n\n+', content)
    full_text_str = "\n\n".join(text_sections)
    removed_blank_line = re.sub(r'(?<!\|)(\n{2,})(?!\|)', '\n', full_text_str)
    process_text = re.sub(r'(?:^|\n)(?<!\n\n)(#{1,6}(?:\s+)?[^\n]*)', r'\n\n\1\n', removed_blank_line)
    processed_text = re.sub(r'(#+ .+)\n{2,}', r'\1\n', process_text)
    return processed_text

# Step 3: Write the modified content to a new Markdown file
def write_markdown(output_file, content):
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(content)

# File paths
input_file = 'docling_output\pdf2.md'  # Input markdown file path
output_file = 'output.md'  # Output markdown file path

# Ensure the input file exists
if not os.path.exists(input_file):
    print(f"Error: {input_file} not found!")
    exit(1)

# Process the markdown content
full_text = read_markdown(input_file)          # Read the original content
processed_text = process_markdown(full_text)   # Perform operations
write_markdown(output_file, processed_text)    # Save the updated content

print(f"Processing complete. Updated markdown saved to {output_file}")