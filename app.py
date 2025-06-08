import streamlit as st
import json
import os
import tempfile
from datetime import datetime
import shutil
from blog_generator import RedditContentProcessor  # Assuming blog_generator.py is in the same directory
from blog_generator import main as blog_generator_main_config # To access default creds
import subprocess
from pathlib import Path
import requests
import base64

# Constants for local file storage
TEMP_DIR = os.path.join(tempfile.gettempdir(), "blog_generator_temp")
IMAGES_DIR = os.path.join(TEMP_DIR, "images")
POSTS_DIR = os.path.join(TEMP_DIR, "posts")

# Ensure temp directories exist
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(POSTS_DIR, exist_ok=True)

# Try to get GitHub PAT from secrets
def get_github_pat():
    try:
        return st.secrets["github_pat"]
    except:
        return ""

# Try to get other secrets
def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except:
        return default

def load_blog_posts():
    """Loads blog posts from JSON files."""
    blog_posts = []
    for filename in os.listdir():
        if filename.endswith(".json") and filename.startswith("blog_post_"):
            try:
                with open(filename, "r") as f:
                    blog_posts.append(json.load(f))
            except json.JSONDecodeError as e:
                st.error(f"Error decoding JSON from {filename}: {e}")
            except Exception as e:
                st.error(f"An error occurred while reading {filename}: {e}")
    return blog_posts


def generate_blog_posts(processor, query):
    """Generates new blog posts using the provided processor."""
    try:
        blog_posts = processor.process_blog_posts(query=query)
        for i, post in enumerate(blog_posts):
            filename = f"blog_post_{datetime.now().strftime('%Y%m%d')}_{i}.json"
            processor.generate_readme(post['body'], f"blog_post_{datetime.now().strftime('%Y%m%d')}_{i}.md")  # Corrected typo here

            with open(filename, 'w') as f:
                json.dump(post, f, indent=2)
        st.success(f"Generated {len(blog_posts)} blog posts and saved to files.")
        return blog_posts
    except Exception as e:
        st.error(f"Error generating blog posts: {e}")
        return []
    

def clear_git_changes():
    """This function is no longer needed as we're using the GitHub API directly."""
    st.warning("This function is not applicable when using the GitHub API directly.")
    return False, "Operation not supported with remote repository."

def validate_post_for_yaml(post):
    """
    Validates post title and description for YAML compatibility.
    Returns (is_valid, error_message) tuple.
    """
    if ':' in post['title']:
        return False, "Title contains a colon (:) which can cause YAML parsing issues. Please remove colons from the title."
    
    if ':' in post['description']:
        return False, "Description contains a colon (:) which can cause YAML parsing issues. Please remove colons from the description."
    
    return True, ""

def view_generated_blogs(blog_posts):
    """Displays generated blog posts with archive, delete, and publish functionality."""
    if not blog_posts:
        st.info("No blog posts found. Generate some!")
        return

    st.write("## Generated Blog Posts")
    for i, post in enumerate(blog_posts):
        filename = f"blog_post_{datetime.now().strftime('%Y%m%d')}_{i}.json"
        st.write(f"### {post['title']}")
        st.write(f"**Description:** {post['description']}")
        st.write(f"**Tags:** {', '.join(post['tags'])}")
        st.write(f"**Categories:** {', '.join(post['categories'])}")

        with st.expander("Show Content"):
            st.markdown(post["body"])

        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("Archive", key=f"archive_{i}"):
                try:
                    os.rename(filename, filename.replace(".json", "_archived.json"))
                    st.success(f"Archived {filename}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error archiving {filename}: {e}")

        with col2:
            if st.button("Delete", key=f"delete_{i}"):
                try:
                    os.remove(filename)
                    md_filename = filename.replace(".json", ".md")
                    if os.path.exists(md_filename):
                        os.remove(md_filename)
                    st.success(f"Deleted {filename}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting {filename}: {e}")
                    
        with col3:
            uploaded_file = st.file_uploader("Upload Image", key=f"image_{i}", type=["png", "jpg", "jpeg"])
            if uploaded_file:
                # Save the image and store its path in session state
                image_path = handle_image_upload(uploaded_file)
                if image_path:
                    st.session_state[f"image_path_{i}"] = image_path
                    st.success("Image uploaded successfully!")
                
        with col4:
            if st.button("Publish Now", key=f"publish_{i}"):
                try:
                    # Validate post for YAML compatibility
                    is_valid, error_message = validate_post_for_yaml(post)
                    if not is_valid:
                        st.error(error_message)
                        continue
                        
                    # Get previously uploaded image path from session state
                    image_path = st.session_state.get(f"image_path_{i}", None)
                    if image_path:
                        # Add image file to git if it exists
                        img_filepath = os.path.join(TEMP_DIR, "assets", image_path)
                        if os.path.exists(img_filepath):
                            img_rel_path = os.path.relpath(img_filepath, TEMP_DIR)
                        
                    # Generate and save the markdown file
                    md_filepath = publish_to_cosmi_blogs(post, image_path)
                    md_rel_path = os.path.relpath(md_filepath, TEMP_DIR)
                    
                    # Get just the filename for commit message
                    filename = os.path.basename(md_filepath)
                    
                    # Collect all files to commit at once
                    files_to_commit = []
                    if image_path:
                        img_filepath = os.path.join(TEMP_DIR, "assets", image_path)
                        if os.path.exists(img_filepath):
                            img_rel_path = os.path.relpath(img_filepath, TEMP_DIR)
                            files_to_commit.append(img_rel_path.replace('\\', '/'))
                    
                    # Add markdown file to commit
                    files_to_commit.append(md_rel_path.replace('\\', '/'))
                    
                    # Use PAT if available, otherwise use regular git
                    github_pat = get_github_pat()
                    github_repo_info = get_secret('github_repo_info', {})
                    
                    if github_pat and github_repo_info:
                        if github_api_commit_and_push(files_to_commit, f"Create Blog \"{os.path.splitext(os.path.basename(md_filepath))[0]}\"", 
                                                    github_pat, github_repo_info):
                            st.success("Blog post and assets published successfully using GitHub API!")
                        else:
                            st.error("Failed to commit and push changes via GitHub API.")
                    else:
                        # Git operations with all files in a single commit
                        if git_commit_and_push(files_to_commit, f"Create Blog \"{os.path.splitext(os.path.basename(md_filepath))[0]}\""):
                            st.success("Blog post and assets published successfully!")
                        else:
                            st.error("Failed to commit and push changes to git.")
                        
                except Exception as e:
                    st.error(f"Error publishing post: {e}")
                    st.error("Exception details: " + str(e.__class__.__name__) + ": " + str(e))


def handle_image_upload(uploaded_file, target_folder=IMAGES_DIR):
    """Handle image upload and return the relative path for blog post."""
    if uploaded_file:
        # Create target folder if it doesn't exist
        os.makedirs(target_folder, exist_ok=True)
        
        # Save file to images directory
        file_extension = uploaded_file.name.split('.')[-1].lower()
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        filepath = os.path.join(target_folder, filename)
        
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        return f"images/{filename}"  # Return relative path for blog post
    return None

def publish_to_cosmi_blogs(post, image_path=None):
    """Convert blog post to cosmi-blogs format and save to temporary directory."""
    # Create markdown content
    tags_str = '\n'.join([f'  - {tag}' for tag in post['tags']])
    categories_str = '\n'.join([f'  - {cat}' for cat in post['categories']])
    
    # Escape colons in title and description for YAML compatibility
    title = post['title'].replace(":", "&#58;")
    description = post['description'].replace(":", "&#58;")
    
    md_content = f"""---
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}
description: "{description}"
tags:
{tags_str}
categories:
{categories_str}
image: {image_path if image_path else "images/blog2.jpg"}
---

{post['body']}

{{< skin-analysis >}}
---  
**Experience personalized skincare recommendations with COSMI Skin! Your skin will thank you!**
"""
    # Save to posts directory
    # Sanitize filename: remove special chars and convert to kebab-case
    filename = post['title'].lower()
    # Replace special characters with empty string
    filename = ''.join(c for c in filename if c.isalnum() or c.isspace())
    # Replace spaces with hyphens and remove multiple hyphens
    filename = '-'.join(filter(None, filename.split(' ')))
    filename = filename + '.md'
    
    filepath = os.path.join(POSTS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    return filepath

def git_commit_and_push(files, commit_message):
    """This function is replaced by github_api_commit_and_push."""
    st.warning("Direct git operations are not supported. Using GitHub API instead.")
    github_pat = get_github_pat()
    github_repo_info = {
        'owner': get_secret('github_owner', ''),
        'repo': get_secret('github_repo', ''),
        'branch': get_secret('github_branch', 'main')
    }
    return github_api_commit_and_push(files, commit_message, github_pat, github_repo_info)

def github_api_commit_and_push(files, commit_message, github_pat, repo_info):
    """Commit and push changes using GitHub API with PAT."""
    try:
        owner = repo_info.get('owner', '')
        repo = repo_info.get('repo', '')
        branch = repo_info.get('branch', 'main')
        
        if not all([owner, repo, branch]):
            st.error("Missing GitHub repository information. Please provide owner, repo, and branch.")
            return False
        
        # For each file we need to commit
        for file_path in files:
            # Get the full path to the local file
            full_path = os.path.join(TEMP_DIR, file_path)
            
            # Determine the correct path in the repository
            # For images, they should go to assets/images
            # For posts, they should go to content/posts
            if file_path.startswith('images/'):
                repo_file_path = f"assets/{file_path}"
            else:
                repo_file_path = f"content/posts/{os.path.basename(file_path)}"
            
            # Read the file content
            with open(full_path, 'rb') as f:
                content = f.read()
            
            # Encode content to base64
            content_base64 = base64.b64encode(content).decode('utf-8')
            
            # Check if file already exists in the repository
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{repo_file_path}"
            headers = {
                'Authorization': f'token {github_pat}',
                'Accept': 'application/vnd.github+json'
            }
            
            # Try to get the file to see if it exists
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # File exists, get its SHA
                file_sha = response.json()['sha']
                
                # Update the file
                data = {
                    'message': commit_message,
                    'content': content_base64,
                    'sha': file_sha,
                    'branch': branch
                }
            else:
                # File doesn't exist, create it
                data = {
                    'message': commit_message,
                    'content': content_base64,
                    'branch': branch
                }
            
            # Make the API request to create/update the file
            response = requests.put(url, headers=headers, json=data)
            
            if response.status_code not in [200, 201]:
                st.error(f"Failed to update file {repo_file_path}: {response.status_code} - {response.text}")
                return False
        
        return True
    except Exception as e:
        st.error(f"GitHub API operation failed: {str(e)}")
        return False

def main():
    st.title("Blog Post Generator")
    
    # GitHub PAT and Repository Settings
    if 'github_repo_info' not in st.session_state:
        st.session_state.github_repo_info = {
            'owner': get_secret('github_owner', ''),
            'repo': get_secret('github_repo', ''),
            'branch': get_secret('github_branch', 'main')
        }
    
    # Add a note about remote repository operation
    st.info("This app publishes directly to your GitHub repository using the GitHub API. No local git repository is required.")
    
    # Add a button to clear temporary files
    if st.button("Clear Temporary Files"):
        try:
            for file in os.listdir(IMAGES_DIR):
                os.remove(os.path.join(IMAGES_DIR, file))
            for file in os.listdir(POSTS_DIR):
                os.remove(os.path.join(POSTS_DIR, file))
            st.success("Temporary files cleared successfully!")
        except Exception as e:
            st.error(f"Error clearing temporary files: {e}")
    
    # --- Load default credentials from blog_generator.py ---
    # This is a bit of a workaround to access the hardcoded creds in blog_generator's main.
    # Ideally, credentials should be managed via a config file or environment variables.
    default_reddit_creds = {
        "client_id": get_secret("reddit_client_id", ""),
        "client_secret": get_secret("reddit_client_secret", ""),
        "user_agent": get_secret("reddit_user_agent", ""),
        "username": get_secret("reddit_username", ""),
        "password": get_secret("reddit_password", ""),
    }
    default_gemini_key = get_secret("gemini_api_key", "")
    # --- End loading default credentials ---

    # Sidebar for API Keys and Credentials
    with st.sidebar:
        st.header("Configuration")
        
        # GitHub PAT Configuration
        st.subheader("GitHub Configuration")
        github_pat = get_github_pat()
        if github_pat:
            st.success("GitHub PAT is configured via secrets ✓")
        else:
            st.error("GitHub PAT not found in secrets. Please add it to your secrets.toml file.")
        
        # Get repo info from secrets or session state
        github_owner = st.text_input("GitHub Repository Owner", 
                                    value=st.session_state.github_repo_info.get('owner', ''))
        
        github_repo = st.text_input("GitHub Repository Name", 
                                   value=st.session_state.github_repo_info.get('repo', ''))
        
        github_branch = st.text_input("GitHub Branch", 
                                     value=st.session_state.github_repo_info.get('branch', 'main'))
        
        # Save GitHub settings to session state
        if github_owner and github_repo:
            st.session_state.github_repo_info = {
                'owner': github_owner,
                'repo': github_repo,
                'branch': github_branch
            }
            
            # Show repository status
            repo_url = f"https://github.com/{github_owner}/{github_repo}"
            st.success(f"Target repository: [Open on GitHub]({repo_url})")
        
        st.subheader("Reddit & Gemini Configuration")
        reddit_client_id = st.text_input("Reddit Client ID", value=default_reddit_creds.get("client_id"), type="password")
        reddit_client_secret = st.text_input("Reddit Client Secret", value=default_reddit_creds.get("client_secret"), type="password")
        reddit_user_agent = st.text_input("Reddit User Agent", value=default_reddit_creds.get("user_agent"))
        reddit_username = st.text_input("Reddit Username", value=default_reddit_creds.get("username"))
        reddit_password = st.text_input("Reddit Password", value=default_reddit_creds.get("password"), type="password")
        gemini_api_key = st.text_input("Gemini API Key", value=default_gemini_key, type="password")

        if not all(
            [
                reddit_client_id,
                reddit_client_secret,
                reddit_user_agent,
                reddit_username,
                reddit_password,
                gemini_api_key,
            ]
        ):
            st.warning("Please provide all API keys and credentials in the sidebar.")
            processor = None
        else:
            reddit_credentials = {
                "client_id": reddit_client_id,
                "client_secret": reddit_client_secret,
                "user_agent": reddit_user_agent,
                "username": reddit_username,
                "password": reddit_password,
            }
            processor = RedditContentProcessor(reddit_credentials, gemini_api_key)

    tab1, tab2 = st.tabs(["Generate Blogs", "View Blogs"])

    with tab1:
        st.header("Generate New Blogs")
        if processor:
            search_query = st.text_input("Enter search query for Reddit discussions:")
            if st.button("Generate"):
                if search_query:
                    generate_blog_posts(processor, search_query)
                else:
                    st.error("Please enter a search query.")
        else:
            st.info("Please provide API keys and credentials in the sidebar to generate blogs.")

    with tab2:
        st.header("View Generated Blogs")
        blog_posts = load_blog_posts()
        view_generated_blogs(blog_posts)


if __name__ == "__main__":
    main()