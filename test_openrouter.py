import os
import sys
from dotenv import load_dotenv

# Ensure src can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ai_analyzer import AIAnalyzer

# Load env
load_dotenv()

def test_connection():
    print(f"--- OpenRouter Connectivity Test ---")
    provider = os.getenv('AI_PROVIDER')
    model = os.getenv('AI_MODEL')
    key = os.getenv('OPENROUTER_API_KEY')
    
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Key present: {'Yes' if key and len(key) > 5 else 'No (or too short)'}")

    if provider != 'openrouter':
        print(f"❌ Error: AI_PROVIDER is set to '{provider}', expected 'openrouter'.")
        return

    try:
        print("\nInitializing AIAnalyzer...")
        analyzer = AIAnalyzer()
        
        if not analyzer.is_available:
            print("❌ AIAnalyzer reports it is NOT available. Check your configuration.")
            return

        print("✅ AIAnalyzer initialized successfully.")
        
        print(f"\nSending test prompt to {model}...")
        # Direct invocation of the underlying LLM object
        # ChatOpenAI supports invoke(str) which converts to HumanMessage
        response = analyzer.llm.invoke("Hello! Verify your identity. Are you the Step 3.5 Flash model?")
        
        print("\n--- 🤖 AI Response ---")
        print(response.content)
        print("----------------------")
        print("\n✅ Test Passed! The Agent is connected to OpenRouter.")

    except Exception as e:
        print(f"\n❌ Test Failed with Exception:")
        print(f"{str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
