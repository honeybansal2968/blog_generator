import traceback
import praw
import os
from google import genai
from google.genai import types
import json
from datetime import datetime
from typing import List, Dict


class RedditContentProcessor:
    def __init__(self, reddit_credentials: Dict, gemini_api_key: str):
        """
        Initialize the Reddit content processor

        Args:
            reddit_credentials: Dict containing client_id, client_secret, user_agent
            gemini_api_key: API key for Gemini
        """
        # Initialize Reddit client
        self.reddit = praw.Reddit(
            client_id=reddit_credentials['client_id'],
            client_secret=reddit_credentials['client_secret'],
            user_agent=reddit_credentials['user_agent'],
            username=reddit_credentials['username'],
            password=reddit_credentials['password']
        )

        # Initialize Gemini with new API structure
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = "gemini-2.5-flash-preview-04-17"  # Updated to latest model

    def fetch_reddit_discussions(self, subreddit_name: str, query: str, limit: int = 20) -> List[Dict]:
        """Search for discussions in a subreddit based on a query"""
        subreddit = self.reddit.subreddit(subreddit_name)
        discussions = []

        # Use search instead of hot
        for submission in subreddit.search(query, sort='relevance', limit=limit):
            if submission.num_comments > 10:
                discussion = {
                    'title': submission.title,
                    'content': submission.selftext,
                    'comments': [],
                    'num_comments': submission.num_comments,
                    'score': submission.score
                }

                # Sort comments by best score
                submission.comment_sort = 'best'
                submission.comments.replace_more(limit=0)

                comment_count = 0
                for comment in submission.comments:
                    if hasattr(comment, 'body') and len(comment.body) > 50:
                        discussion['comments'].append(comment.body)
                        comment_count += 1
                        if comment_count >= 10:
                            break

                if len(discussion['comments']) > 0:
                    discussions.append(discussion)

        return discussions

    def generate_readme(self, content: str, filename: str = "README.md"):
        """Generates a README.md file with the given content."""
        try:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(content)
            print(f"README file '{filename}' has been generated successfully.")
        except Exception as e:
            print(f"An error occurred while writing the file: {e}")

    def generate_blog_content(self, discussion: Dict) -> Dict:
        """Generate blog content using Gemini according to specified schema"""
        prompt = f"""
        Create a blog post about skincare based on this Reddit discussion = {discussion}.
        This discussion has {discussion['num_comments']} total comments and a score of {discussion['score']}.
        # Markdown Cheat Sheet 📜

        Markdown is a lightweight markup language for formatting text. Below are common elements you can use.

        ---

        ## 1. Headings
        ```markdown
        ## H2 Heading
        ### H3 Heading
        #### H4 Heading
        ##### H5 Heading
        ###### H6 Heading
        ** for bold

        Format the output as a JSON object with the following schema:
        {{
            "title": "SEO-optimized title without colon",
            "description": "Meta description (155 characters max) without colon",
            "tags": list of relevant tags,
            "categories": primary categories for this blog,
            "body": body in markdown format
        }}

        Key requirements:
        1. Target website: cosmi.skin
        2. Tags should be relevant skincare keywords
        3. Categories should be broader classifications (e.g., "Skincare", "Product Reviews", "Ingredients")
        4. Body Formatting:
            - Strictly in **Markdown** format (use `#` for headings, `*` for bullet points, etc.).
            - **Do NOT** use JSON or any structured markup inside the body.
            - **Do NOT** use special characters like /u2019 instead use proper punctuation, etc.
            - **Ensure proper markdown hierarchy** with headings, subheadings, and lists where necessary.
        5. Include insights from Reddit comments

        Rules to follow while generating the blog:
        1. Do not use word 'Reddit' or Reddit users anywhere.
        Discussion content
        2. Blog should be SEO optimized.
        """

        # Using new Gemini API structure
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]

        # Set up schema for JSON response
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=1.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                
                properties={
                    "title": types.Schema(type=types.Type.STRING),
                    "description": types.Schema(type=types.Type.STRING),
                    "tags": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING)  # This was missing
                    ),
                    "categories": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING)  # This was missing
                    ),
                    "body": types.Schema(type=types.Type.STRING)
                }
            )
        )

        try:
            # Generate initial content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=generate_content_config
            )
            print("Generated initial content...", response.text[:100])
            # Request improvement with the same schema
            improvement_prompt = "Improve the quality of your blog post. keeping the same json structure."
            contents.append(types.Content(
                role="model",
                parts=[types.Part.from_text(text=response.text)]
            ))
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=improvement_prompt)]
            ))

            improved_response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=generate_content_config
            )
            print("Generated improved content...", improved_response.text[:100])
            # Parse the response as JSON
            blog_post = json.loads(improved_response.text)

            # Validate required fields
            required_fields = ['title', 'description', 'tags', 'categories', 'body']
            for field in required_fields:
                if field not in blog_post:
                    raise KeyError(f"Missing required field: {field}")

            blog_post['body'] = self.convert_escaped_newlines(blog_post['body'])
            return blog_post

        except Exception as e:
            traceback.print_exc()
            # Fallback if JSON parsing fails
            body = response.text if 'response' in locals() else "Error generating content"
            body = self.convert_escaped_newlines(body)
            return {
                'title': discussion['title'],
                'description': discussion['content'][:155] + '...' if len(discussion['content']) > 155 else discussion['content'],
                'tags': ['skincare'],
                'categories': ['General Skincare'],
                'body': body
            }

    def convert_escaped_newlines(self, text):
        # Replace the literal '\n' with actual newlines
        converted_text = text.replace('\\n', '\n')
        return converted_text

    def process_blog_posts(self, subreddit_name: str= "SkincareAddiction", query: str="skincare product review") -> List[Dict]:
        """Process multiple Reddit discussions into blog posts based on a search query"""
        discussions = self.fetch_reddit_discussions(subreddit_name, query)

        blog_posts = []
        for discussion in discussions:
            blog_post = self.generate_blog_content(discussion)
            blog_posts.append(blog_post)
        return blog_posts

def main():
    # Configuration
    reddit_credentials = {
        "client_id": "BxVf0MKUg1zqFnCGGNUsXw",
        "client_secret": "NUaWgvj1ccjxvATA9ILpf9571HFilA",
        "user_agent": "scrapingBeautifully",
        "password": '&honeyB90',
        "username": 'Apprehensive_Buy9768',
    }

    # Get Gemini API key from environment variable or set directly
    gemini_api_key = "AIzaSyA6HGrBLxE2KrRH5uHLN216d1pT9TWnr1s"

    # Initialize processor
    processor = RedditContentProcessor(reddit_credentials, gemini_api_key)

    # Define the search query for skincare products
    search_query = "Minimalist anti acne"

    # Generate blog posts based on the search query
    blog_posts = processor.process_blog_posts(query=search_query)

    # Save blog posts
    for i, post in enumerate(blog_posts):
        filename = f"blog_post_{datetime.now().strftime('%Y%m%d')}_{i}.json"
        processor.generate_readme(post['body'], f"blog_post_{datetime.now().strftime('%Y%m%d')}_{i}.md")

        with open(filename, 'w') as f:
            json.dump(post, f, indent=2)

if __name__ == "__main__":
    main()