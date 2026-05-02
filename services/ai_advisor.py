import os
import logging
from typing import List, Dict, Any
from .explainability_service import ExplainableReport

logger = logging.getLogger(__name__)

class AICreditAdvisor:
    """AI Credit Advisor using Gemini 1.5 Flash (Free Tier) with fallback."""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = None
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except ImportError:
                logger.warning("google-generativeai not installed. Using template fallback.")

    async def generate_advice(self, report: ExplainableReport) -> str:
        """Generates advice using AI if available, else template."""
        if self.model:
            try:
                prompt = self._build_prompt(report)
                response = await self.model.generate_content_async(prompt)
                return response.text
            except Exception as e:
                logger.error(f"AI Generation failed: {e}")
                
        return self._get_template_advice(report)

    def _build_prompt(self, report: ExplainableReport) -> str:
        return f"""
        Role: Senior Credit Risk Analyst.
        User Score: {report.final_score}/900.
        SHAP Contributions: {report.contributions}.
        Positive Factors: {report.factors_improving}.
        Negative Factors: {report.factors_reducing}.
        Constraints: {report.system_constraints}.
        
        Task: Provide 3 short, punchy, actionable advice points to improve this specific Axiom score. 
        Focus on specific neighborhood interactions and stability anchors.
        """

    def _get_template_advice(self, report: ExplainableReport) -> str:
        advice_blocks = []
        
        # 1. General Profile Standing
        if report.final_score >= 800:
            advice_blocks.append("Elite profile. Your high-trust interactions are your strongest assets.")
        elif report.final_score >= 700:
            advice_blocks.append("Strong Prime standing, but hindered by system constraints or missing anchors.")
        else:
            advice_blocks.append("Your profile is in the 'Building' phase. High-impact changes are required below.")

        # 2. Targeted SHAP Insights
        contributions = report.contributions
        
        # S_T (Transitive Trust) Issues
        st_pts = contributions.get("Transitive Trust (S_T)", 0)
        if st_pts < 100:
            advice_blocks.append("- **Improve Network Trust**: Your current peer-to-peer trust linkage is weak. Linking a verified Parent VPA or an Institutional Landlord can provide a stability anchor.")
            
        # S_B (Behavioral) Issues
        sb_pts = contributions.get("Utility Discipline (S_B)", 0)
        if sb_pts < 150:
            advice_blocks.append("- **Build Utility Discipline**: We detected low utility payment activity. Ensuring electricity and broadband bills are paid through this account will build a 'Behavioral Baseline' faster.")
            
        # Risk Impact
        risk_pts = contributions.get("Behavioral Risk Penalty", 0)
        if risk_pts < 0:
             advice_blocks.append(f"- **Mitigate Risk Signals**: Your profile has a {risk_pts} pt drag from high-risk merchant categories. Transitioning spend to GST-verified pharmacies or supermarkets will offset this.")

        # 3. System Constraints
        if report.system_constraints:
            for constraint in report.system_constraints:
                if "Proxy Anchor" in constraint:
                    advice_blocks.append("- **Unlock Elite Tier**: Your score is currently capped at 720. To reach 800+, please upload a corporate salary slip or proof of fixed income.")
                if "Confidence" in constraint:
                    advice_blocks.append("- **Data Density Required**: Your score is gated due to low transaction volume. 3 months of consistent activity is needed to unlock full confidence.")

        return "\n".join(advice_blocks)

    async def get_gpt_formatted_advice(self, report: ExplainableReport) -> str:
        advice = await self.generate_advice(report)
        header = "╔══════════════════════════════════════════════╗\n"
        header += "║ AXIOM AI ADVISOR (Gemini 1.5 Flash)          ║\n"
        header += "╚══════════════════════════════════════════════╝\n"
        return header + advice
