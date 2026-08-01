```python
import streamlit as st
from google import genai
from google.genai import types
import plotly.graph_objects as go
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Business Idea Validator",
    page_icon="🚀",
    layout="wide"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f0f1a; }
    .stApp { background-color: #0f0f1a; color: #ffffff; }

    .hero-title {
        font-size: 2.8rem;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .hero-sub {
        text-align: center;
        color: #888;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    .persona-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border: 1px solid #2a2a4a;
        border-radius: 16px;
        padding: 1.4rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .persona-card:hover { border-color: #667eea; transform: translateY(-2px); }

    .persona-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 0.8rem;
    }
    .persona-emoji { font-size: 2rem; }
    .persona-name { font-size: 1.1rem; font-weight: 600; color: #ffffff; }
    .persona-role { font-size: 0.8rem; color: #888; }

    .score-pill {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .score-high { background: #1a4a2e; color: #4ade80; border: 1px solid #4ade80; }
    .score-mid  { background: #4a3a1a; color: #fbbf24; border: 1px solid #fbbf24; }
    .score-low  { background: #4a1a1a; color: #f87171; border: 1px solid #f87171; }

    .feedback-text { color: #cccccc; font-size: 0.92rem; line-height: 1.6; }

    .verdict-box {
        background: linear-gradient(135deg, #1a1a3e, #2a1a4e);
        border: 2px solid #667eea;
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin-top: 2rem;
    }
    .verdict-score {
        font-size: 4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .verdict-label { font-size: 1.3rem; font-weight: 600; color: #ffffff; margin-bottom: 1rem; }
    .verdict-text  { color: #aaaacc; font-size: 0.95rem; line-height: 1.7; }

    .stTextArea textarea {
        background-color: #1a1a2e !important;
        color: #ffffff !important;
        border: 1px solid #2a2a4a !important;
        border-radius: 12px !important;
        font-size: 1rem !important;
    }
    .stTextInput input {
        background-color: #1a1a2e !important;
        color: #ffffff !important;
        border: 1px solid #2a2a4a !important;
        border-radius: 12px !important;
    }
    div.stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.7rem 2.5rem;
        font-size: 1.05rem;
        font-weight: 600;
        width: 100%;
        transition: opacity 0.2s;
    }
    div.stButton > button:hover { opacity: 0.88; }

    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #ffffff;
        margin: 2rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #2a2a4a;
    }
    .stSpinner > div { border-top-color: #667eea !important; }
</style>
""", unsafe_allow_html=True)

# ── Persona definitions ───────────────────────────────────────────────────────
PERSONAS = [
    {
        "emoji": "💰",
        "name": "Venture Capitalist",
        "role": "Investor & Funding Expert",
        "prompt": (
            "You are a hard-nosed Silicon Valley venture capitalist who has seen thousands of pitches. "
            "Evaluate this startup idea from an investment perspective. Focus on market size, scalability, "
            "return potential, and competitive moat. Be direct and brutal but constructive."
        ),
    },
    {
        "emoji": "🛒",
        "name": "Target Customer",
        "role": "End User Perspective",
        "prompt": (
            "You are a real potential customer for this product. Evaluate whether you would actually use and pay for it. "
            "Focus on pain points solved, usability, pricing, and real-world value. Be honest about what excites or "
            "concerns you as a user."
        ),
    },
    {
        "emoji": "⚔️",
        "name": "Competitor CEO",
        "role": "Market Threat Analysis",
        "prompt": (
            "You are the CEO of an existing company that would compete with this startup. "
            "Analyze their weaknesses, how easily you could copy or crush them, and what "
            "competitive advantages or threats this idea poses. Be strategic and ruthless."
        ),
    },
    {
        "emoji": "📊",
        "name": "Market Analyst",
        "role": "Data & Trends Expert",
        "prompt": (
            "You are a senior market research analyst. Evaluate this idea based on market trends, "
            "timing, TAM/SAM/SOM potential, industry dynamics, and macro factors. "
            "Reference relevant market data and trends in your analysis."
        ),
    },
    {
        "emoji": "😈",
        "name": "Devil's Advocate",
        "role": "Worst-Case Scenario",
        "prompt": (
            "You are the ultimate devil's advocate. Your job is to find every possible way this idea could fail. "
            "Think about regulation, timing, execution risks, black swan events, and fundamental flaws. "
            "Be creative and thorough in your criticism."
        ),
    },
]

DIMENSIONS = ["Market Size", "Uniqueness", "Feasibility", "Profitability", "Timing", "Team Risk"]

# ── Gemini helpers ────────────────────────────────────────────────────────────
def get_persona_feedback(idea: str, persona: dict, api_key: str) -> dict:
    client = genai.Client(api_key=api_key)
    prompt = f"""
{persona['prompt']}

Startup idea: {idea}

Respond with a JSON object matching this schema:
{{
  "score": integer (1-10),
  "headline": string (one punchy sentence summary),
  "feedback": string (3-4 sentences of detailed feedback),
  "best_point": string (single strongest aspect),
  "biggest_risk": string (single biggest threat)
}}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(response.text)


def get_radar_scores(idea: str, api_key: str) -> dict:
    client = genai.Client(api_key=api_key)
    prompt = f"""
You are a startup evaluation expert. Score this startup idea on exactly these 6 dimensions from 1 to 10.

Startup idea: {idea}

Respond with a JSON object matching this schema:
{{
  "Market Size": integer,
  "Uniqueness": integer,
  "Feasibility": integer,
  "Profitability": integer,
  "Timing": integer,
  "Team Risk": integer
}}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(response.text)


def get_final_verdict(idea: str, feedbacks: list, api_key: str) -> dict:
    client = genai.Client(api_key=api_key)
    summaries = "\n".join(
        [f"- {p['name']} (score {f['score']}/10): {f['headline']}" for p, f in feedbacks]
    )
    prompt = f"""
You are a startup mentor synthesising expert panel feedback.

Startup idea: {idea}

Panel verdicts:
{summaries}

Respond with a JSON object matching this schema:
{{
  "overall_score": integer (1-100),
  "label": string ("Brilliant", "Promising", "Needs Work", "Risky", or "Avoid"),
  "summary": string (3-4 sentences synthesising all feedback),
  "next_steps": list of 3 strings (actionable next steps)
}}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(response.text)


# ── Score pill helper ─────────────────────────────────────────────────────────
def score_class(score: int) -> str:
    if score >= 7:
        return "score-high"
    if score >= 4:
        return "score-mid"
    return "score-low"


# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">🚀 AI Business Idea Validator</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">5 expert AI personas brutally critique your startup idea</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input("Gemini API Key", type="password", placeholder="paste your key here...")
    st.markdown("---")
    st.markdown("**How it works:**")
    st.markdown("1. Enter your API key\n2. Describe your startup idea\n3. Get feedback from 5 AI experts\n4. See your visual scorecard")
    st.markdown("---")
    st.markdown("*Free tier: 1,500 requests/day*")

idea = st.text_area(
    "Describe your startup idea",
    placeholder="e.g. An app that connects local farmers directly to urban consumers, letting people subscribe to weekly fresh produce boxes with real-time farm tracking...",
    height=140,
)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    run = st.button("🔍 Validate My Idea")

if run:
    if not api_key:
        st.error("Please enter your Gemini API key in the sidebar.")
    elif not idea.strip():
        st.error("Please describe your startup idea first.")
    else:
        st.markdown('<div class="section-title">Expert Panel Feedback</div>', unsafe_allow_html=True)

        feedbacks = []
        
        with st.spinner("Analyzing your idea across 5 AI expert personas simultaneously..."):
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_persona = {
                    executor.submit(get_persona_feedback, idea, persona, api_key): persona 
                    for persona in PERSONAS
                }
                
                results_map = {}
                for future in as_completed(future_to_persona):
                    persona = future_to_persona[future]
                    try:
                        results_map[persona["name"]] = (persona, future.result())
                    except Exception as e:
                        st.error(f"Error getting feedback from {persona['name']}: {e}")

        cols = st.columns(2)
        for i, persona in enumerate(PERSONAS):
            if persona["name"] in results_map:
                p, result = results_map[persona["name"]]
                feedbacks.append((p, result))
                col = cols[i % 2] if i < 4 else st.columns([1])[0]
                with col:
                    sc = score_class(result["score"])
                    st.markdown(f"""
<div class="persona-card">
  <div class="persona-header">
    <span class="persona-emoji">{p['emoji']}</span>
    <div>
      <div class="persona-name">{p['name']}</div>
      <div class="persona-role">{p['role']}</div>
    </div>
  </div>
  <span class="score-pill {sc}">Score: {result['score']}/10 — {result['headline']}</span>
  <div class="feedback-text">{result['feedback']}</div>
  <div style="display:flex; gap:1rem; margin-top:0.8rem;">
    <div style="flex:1; background:#1a2a1a; border-radius:10px; padding:0.7rem;">
      <div style="font-size:0.75rem; color:#4ade80; font-weight:600; margin-bottom:3px;">✅ Best Point</div>
      <div style="font-size:0.82rem; color:#cccccc;">{result['best_point']}</div>
    </div>
    <div style="flex:1; background:#2a1a1a; border-radius:10px; padding:0.7rem;">
      <div style="font-size:0.75rem; color:#f87171; font-weight:600; margin-bottom:3px;">⚠️ Biggest Risk</div>
      <div style="font-size:0.82rem; color:#cccccc;">{result['biggest_risk']}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        if len(feedbacks) == 5:
            st.markdown('<div class="section-title">📡 Scorecard Radar</div>', unsafe_allow_html=True)

            with st.spinner("Generating visual scorecard..."):
                try:
                    radar = get_radar_scores(idea, api_key)
                    values = [radar.get(d, 5) for d in DIMENSIONS]
                    values_closed = values + [values[0]]
                    dims_closed  = DIMENSIONS + [DIMENSIONS[0]]

                    fig = go.Figure()
                    fig.add_trace(go.Scatterpolar(
                        r=values_closed,
                        theta=dims_closed,
                        fill="toself",
                        fillcolor="rgba(102,126,234,0.25)",
                        line=dict(color="#667eea", width=2.5),
                        marker=dict(size=7, color="#f093fb"),
                        name="Your Idea",
                    ))
                    fig.update_layout(
                        polar=dict(
                            bgcolor="#1a1a2e",
                            radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(color="#888", size=10), gridcolor="#2a2a4a", linecolor="#2a2a4a"),
                            angularaxis=dict(tickfont=dict(color="#cccccc", size=12), gridcolor="#2a2a4a", linecolor="#2a2a4a"),
                        ),
                        paper_bgcolor="#0f0f1a",
                        plot_bgcolor="#0f0f1a",
                        font=dict(color="#ffffff"),
                        showlegend=False,
                        margin=dict(t=40, b=40, l=60, r=60),
                        height=420,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Radar chart error: {e}")

            st.markdown('<div class="section-title">🏆 Final Verdict</div>', unsafe_allow_html=True)

            with st.spinner("Writing final verdict..."):
                try:
                    verdict = get_final_verdict(idea, feedbacks, api_key)
                    next_steps_html = "".join(
                        [f'<div style="background:#1a1a2e; border-left: 3px solid #667eea; border-radius:8px; padding:0.6rem 1rem; margin:0.4rem 0; color:#cccccc; font-size:0.9rem;">→ {s}</div>' for s in verdict.get("next_steps", [])]
                    )
                    st.markdown(f"""
<div class="verdict-box">
  <div class="verdict-score">{verdict['overall_score']}</div>
  <div style="color:#888; font-size:0.85rem; margin-top:-0.5rem; margin-bottom:0.5rem;">out of 100</div>
  <div class="verdict-label">{verdict['label']}</div>
  <div class="verdict-text">{verdict['summary']}</div>
  <div style="margin-top:1.5rem; text-align:left;">
    <div style="font-size:0.85rem; font-weight:600; color:#667eea; margin-bottom:0.5rem; text-transform:uppercase; letter-spacing:0.05em;">Recommended Next Steps</div>
    {next_steps_html}
  </div>
</div>
""", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Verdict error: {e}")
