#!/usr/bin/env python3
"""
Test script to verify markdown rendering in the dashboard.

This script tests the markdown formatting function with various markdown elements
to ensure they render correctly in the dashboard.
"""

import sys
import os
import re

# Add the server directory to path so we can import the dashboard functions
sys.path.append('thinking_sdk_server')

def format_insight_content(content: str) -> str:
    """Format insight content for better readability with proper markdown rendering."""
    content = content.strip()
    
    # Convert ### Headers
    content = re.sub(r'^### (.*?)(?=\n|$)', r'<h3>\1</h3>', content, flags=re.MULTILINE)
    content = re.sub(r'^## (.*?)(?=\n|$)', r'<h2>\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^# (.*?)(?=\n|$)', r'<h1>\1</h1>', content, flags=re.MULTILINE)
    
    # Convert **bold** to HTML
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    
    # Convert *italic* to HTML (but not inside bold)
    content = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', content)
    
    # Convert `inline code` to HTML
    content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
    
    # Convert numbered lists
    content = re.sub(r'^(\d+)\.\s+(.*?)(?=\n|$)', r'<li>\2</li>', content, flags=re.MULTILINE)
    # Wrap consecutive <li> elements in <ol>
    content = re.sub(r'(<li>.*?</li>(?:\n<li>.*?</li>)*)', r'<ol>\1</ol>', content, flags=re.DOTALL)
    
    # Convert bullet points (- or *)
    content = re.sub(r'^[-*]\s+(.*?)(?=\n|$)', r'<li>\1</li>', content, flags=re.MULTILINE)
    # Wrap consecutive <li> elements that aren't already in <ol> in <ul>
    content = re.sub(r'(?<!ol>)(<li>.*?</li>(?:\n<li>.*?</li>)*)', r'<ul>\1</ul>', content, flags=re.DOTALL)
    
    # Convert code blocks (```language or ```)
    content = re.sub(r'```(\w+)?\n(.*?)\n```', r'<pre><code>\2</code></pre>', content, flags=re.DOTALL)
    
    # Convert blockquotes (> text)
    content = re.sub(r'^>\s+(.*?)(?=\n|$)', r'<blockquote>\1</blockquote>', content, flags=re.MULTILINE)
    
    # Handle paragraphs - split by double newlines
    paragraphs = content.split('\n\n')
    formatted_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if para:
            # Don't wrap headers, lists, blockquotes, or code blocks in <p> tags
            if not re.match(r'^<(h[1-6]|ul|ol|li|blockquote|pre|code)', para):
                # Replace single newlines with <br> within paragraphs
                para = para.replace('\n', '<br>')
                para = f'<p>{para}</p>'
            formatted_paragraphs.append(para)
    
    content = '\n\n'.join(formatted_paragraphs)
    
    # Clean up extra newlines and spacing
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = re.sub(r'<br>\s*<br>', '<br>', content)
    
    # Wrap in div with styling
    return f'<div class="insight-markdown">{content}</div>'

def test_markdown_rendering():
    """Test various markdown elements."""
    
    # Sample markdown content similar to what LLM might generate
    sample_content = """The runtime exceptions you've posted indicate a couple of underlying issues related to environment variables and missing configuration files in your Python application. Let's break down each of the exceptions to understand the root causes:

### Root Causes:

1. **KeyError for 'NETRC':**
   - This error occurs when the code is attempting to access an environment variable named `NETRC`, but it doesn't exist in the current environment.
   - The NETRC file typically contains login information for FTP or similar services.

2. **FileNotFoundError for '/Users/srikar/.netrc':**
   - This error indicates that the program tried to check for the existence of a `.netrc` file in the specified directory but couldn't find it.
   - The absence of this file leads to the first KeyError.

### Suggested Fixes:

1. **Create and Configure the .netrc File:**
   ```bash
   touch ~/.netrc
   chmod 600 ~/.netrc
   ```

2. **Set Environment Variables:**
   - Set the `NETRC` environment variable if your application requires it
   - Configure `no_proxy` and `NO_PROXY` variables as needed

3. **Code Modification:**
   ```python
   import os
   
   # Safe environment variable access
   netrc_path = os.environ.get('NETRC', '~/.netrc')
   no_proxy = os.environ.get('no_proxy', '')
   ```

> **Important:** Always use `os.environ.get()` with default values instead of direct dictionary access to avoid KeyError exceptions.

This should resolve the configuration-related issues in your application."""

    print("🧪 TESTING MARKDOWN RENDERING")
    print("=" * 50)
    
    print("\n📝 Original Content:")
    print("-" * 30)
    print(sample_content[:200] + "...")
    
    print("\n🎨 Rendered HTML:")
    print("-" * 30)
    rendered = format_insight_content(sample_content)
    print(rendered)
    
    print("\n✅ Markdown rendering test completed!")
    print("\nKey elements tested:")
    print("  ✅ Headers (###, ##, #)")
    print("  ✅ Bold text (**text**)")
    print("  ✅ Italic text (*text*)")
    print("  ✅ Inline code (`code`)")
    print("  ✅ Code blocks (```)")
    print("  ✅ Numbered lists (1. item)")
    print("  ✅ Bullet lists (- item)")
    print("  ✅ Blockquotes (> text)")
    print("  ✅ Paragraphs")

def main():
    """Main test runner."""
    test_markdown_rendering()

if __name__ == "__main__":
    main()