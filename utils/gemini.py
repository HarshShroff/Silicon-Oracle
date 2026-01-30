import streamlit as st
from google import genai
from google.genai import types
from datetime import datetime
# Alias to avoid conflict if needed, or just use clean imports
import google.generativeai as google_genai


class GeminiAnalyzer:
    def __init__(self):
        try:
            # AUTO-FIX: Use BYOK keys if available
            from utils.auth import get_user_decrypted_keys, is_logged_in

            api_key = None
            if is_logged_in():
                user_keys = get_user_decrypted_keys()
                api_key = user_keys.get("gemini_api_key")

            if not api_key:
                api_key = st.secrets.get("gemini", {}).get("api_key")

            # Initialize the new Client
            self.client = genai.Client(api_key=api_key)
            self.model_name = "gemini-2.0-flash"  # Use a model that supports search
        except Exception as e:
            st.error(f"❌ Gemini Connection Failed: {e}")
            self.client = None

    def analyze_ticker(self, ticker):
        """
        Analyzes a stock using Google Search Grounding.
        The AI performs its own web search to find the latest news.
        """
        if not self.client:
            return "AI Not Connected", 0.0, "Neutral"

        current_date = datetime.now().strftime("%B %d, %Y")

        # 1. Define the Grounding Tool
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        # 2. The Prompt (No need to feed it news text!)
        prompt = f"""
        Today is {current_date}.
        
        Perform a Google Search for the latest news, risks, and catalysts for {ticker} stock.
        
        Based *only* on the search results, provide:
        1. A brief summary of the most critical news from the last 7 days.
        2. Top 2 Bullish Catalysts.
        3. Top 2 Bearish Risks.
        4. A final Sentiment Score (0 to 100) and Label (Bullish/Bearish/Neutral).
        
        Format the output clearly.
        """

        try:
            # 3. Generate Content with Grounding
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                )
            )

            # 4. Extract Text & Grounding Metadata
            analysis_text = response.text

            # Simple Sentiment Parsing (The AI is smart enough to state it)
            # We look for the score in the text to populate the gauge
            score = 50
            label = "Neutral"

            if "Score:" in analysis_text:
                try:
                    # quick parse logic: find "Score: 75"
                    import re
                    match = re.search(r"Score:\s*(\d+)", analysis_text)
                    if match:
                        score = int(match.group(1))
                        if score > 60:
                            label = "Bullish"
                        elif score < 40:
                            label = "Bearish"
                except:
                    pass

            # 5. Add Citations (Optional but cool)
            # The response object contains citation metadata you can parse if you want rich links
            # For now, we return the raw text which usually contains inline citations like [1]

            return analysis_text, score, label

        except Exception as e:
            return f"AI Error: {e}", 0, "Error"


# Removed cache because client is user-specific
def get_ai():
    return GeminiAnalyzer()


def analyze_with_gemini(prompt: str) -> str:
    """
    Simple function to analyze text with Gemini.
    Used by AI Scanner for factor analysis.
    """
    try:
        import google.generativeai as genai

        # AUTO-FIX: Use BYOK keys
        from utils.auth import get_user_decrypted_keys, is_logged_in

        api_key = None
        if is_logged_in():
            user_keys = get_user_decrypted_keys()
            api_key = user_keys.get("gemini_api_key")

        if not api_key:
            api_key = st.secrets.get("gemini", {}).get("api_key")

        genai.configure(api_key=api_key)

        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)

        return response.text
    except Exception as e:
        return f"AI Error: {e}"
