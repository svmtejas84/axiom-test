from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

@dataclass
class ExplainableReport:
    base_value: int = 300
    final_score: int = 300
    contributions: Dict[str, int] = field(default_factory=dict)
    factors_improving: List[str] = field(default_factory=list)
    factors_reducing: List[str] = field(default_factory=list)
    system_constraints: List[str] = field(default_factory=list)
    
    def generate_waterfall(self) -> List[str]:
        """Generates a human-readable waterfall trace."""
        lines = [f"Base Value: {self.base_value}"]
        current = self.base_value
        for feat, pts in self.contributions.items():
            sign = "+" if pts >= 0 else ""
            current += pts
            lines.append(f"  {feat:<25}: {sign}{pts} pts -> {current}")
        return lines

class ExplainabilityService:
    """Lightweight SHAP-inspired interpretability module."""
    
    @staticmethod
    def explain(
        base_value: int,
        final_score: int,
        contributions: Dict[str, int],
        metadata: Dict[str, Any] = None
    ) -> ExplainableReport:
        report = ExplainableReport(
            base_value=base_value,
            final_score=final_score,
            contributions=contributions
        )
        metadata = metadata or {}
        
        # Mapping mathematical contributions to human-readable strings
        for feat, pts in contributions.items():
            if pts > 0:
                if "S_T" in feat:
                    report.factors_improving.append(f"Trust Linkage: interaction with reputable nodes (+{pts} pts)")
                elif "S_B" in feat:
                    report.factors_improving.append(f"Utility Discipline: consistent payment behavior (+{pts} pts)")
                elif "S_N" in feat:
                    report.factors_improving.append(f"Neighborhood Density: strong local world integration (+{pts} pts)")
                elif "Shield" in feat:
                    report.factors_improving.append(f"Identity Shield: verification mitigated family risk (+{pts} pts)")
                elif "Anchor" in feat:
                    report.factors_improving.append(f"Institutional Anchor: verified landlord agreement (+{pts} pts)")
                elif "Parental" in feat:
                    report.factors_improving.append(f"Trust Inheritance: linked to reputable node (+{pts} pts)")
                else:
                    report.factors_improving.append(f"{feat} (+{pts} pts)")
            elif pts < 0:
                if "Risk" in feat or "Penalty" in feat:
                    report.factors_reducing.append(f"Behavioral Risk: high-risk merchant profile detected ({pts} pts)")
                elif "Missing" in feat:
                    report.factors_reducing.append(f"Stability Gap: missing residency validation ({pts} pts)")
                elif "Parental" in feat:
                    report.factors_reducing.append(f"Trust Inheritance: linked to low-reputation node ({pts} pts)")
                else:
                    report.factors_reducing.append(f"{feat} ({pts} pts)")
        
        # System Constraints
        if metadata.get("proxy_cap_applied"):
            limit = metadata.get("proxy_cap_value", 720)
            report.system_constraints.append(f"Proxy Anchor: Score capped at {limit} due to missing fixed income proof.")
            
        if metadata.get("confidence_gate_applied"):
            report.system_constraints.append("Confidence Gate: Score capped at 650 due to insufficient behavioral signals.")
            
        return report
