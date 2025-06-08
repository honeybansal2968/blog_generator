# Running Blog Generator with Ngrok

This guide explains how to make your Blog Generator app accessible from anywhere on the internet using ngrok.

## Prerequisites

1. Sign up for a free ngrok account at https://ngrok.com/
2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken

## Static Domain Configuration

The application is configured to use a specific static domain:

```
wahoo-unified-oyster.ngrok-free.app
```

This means your app will always be accessible at this URL whenever the ngrok tunnel is running, rather than getting a random URL each time.

## Option 1: Run Streamlit and Ngrok Together

This option starts both the Streamlit app and ngrok tunnel in one command:

```bash
python run_with_ngrok.py
```

You'll be prompted to enter your ngrok authtoken if it's not set as an environment variable.

## Option 2: Run Separately (Recommended)

This option gives you more control by running Streamlit and ngrok separately:

1. First, start the Streamlit app:

```bash
streamlit run app.py
```

2. In a separate terminal, start the ngrok tunnel:

```bash
python ngrok_tunnel.py
```

You'll be prompted to enter your ngrok authtoken if it's not set as an environment variable.

## Setting Ngrok Authtoken as Environment Variable

To avoid entering your authtoken each time, set it as an environment variable:

### Windows

```
set NGROK_AUTH_TOKEN=your_authtoken_here
```

### macOS/Linux

```
export NGROK_AUTH_TOKEN=your_authtoken_here
```

## Notes

- Using a static domain requires that your ngrok account is properly configured with this domain.
- Make sure you're logged into the correct ngrok account that owns the `wahoo-unified-oyster.ngrok-free.app` domain.
- If you get an error about the domain being unavailable, check that:

  1. You're using the correct authtoken
  2. The domain is actually reserved in your account
  3. No other tunnel is currently using this domain

- The free tier of ngrok has some limitations, including:

  - Session length of 2 hours
  - Random URLs (cannot specify custom subdomain)
  - Limited connections per minute

- For production use, consider upgrading to a paid ngrok plan or using a proper hosting service like Streamlit Cloud.

- Make sure your `.streamlit/secrets.toml` file is properly configured with all required API keys.
