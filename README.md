# Blog Generator App

A Streamlit application for generating blog posts using Reddit content and Gemini AI, with GitHub integration for publishing.

## Local Development

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up your secrets:

   - Create a `.streamlit/secrets.toml` file with your API keys and credentials
   - Use the template in `.streamlit/secrets.toml` as a reference

4. Run the app:
   ```
   streamlit run app.py
   ```

## Streamlit Cloud Deployment

1. Push your code to GitHub (make sure to exclude your local `.streamlit/secrets.toml` from git)
2. Log in to [Streamlit Cloud](https://streamlit.io/cloud)
3. Create a new app and connect it to your GitHub repository
4. In the Streamlit Cloud dashboard:
   - Go to your app settings
   - Add all the secrets from your local `.streamlit/secrets.toml` file
   - Deploy the app

## Required Secrets

- `github_pat`: Your GitHub Personal Access Token with repo permissions
- `github_owner`: GitHub username or organization name
- `github_repo`: Repository name
- `github_branch`: Branch name (default: main)
- `reddit_client_id`: Reddit API client ID
- `reddit_client_secret`: Reddit API client secret
- `reddit_user_agent`: Reddit API user agent
- `reddit_username`: Reddit username
- `reddit_password`: Reddit password
- `gemini_api_key`: Google Gemini API key

## Features

- Generate blog posts using Reddit content and Gemini AI
- Upload images for blog posts
- Publish blog posts directly to GitHub
- Clear git changes
- Support for GitHub Personal Access Token for secure deployment
