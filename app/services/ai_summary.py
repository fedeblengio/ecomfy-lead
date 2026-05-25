import os
from openai import OpenAI


def generate_summary(metrics: dict) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    client = OpenAI(api_key=api_key)

    prompt = f"""You are an operations analyst for a lead distribution company.
Based on these daily metrics, provide a brief executive summary with:
1. General overview (2-3 sentences)
2. Main problems identified
3. Recommended actions

Metrics:
- Total leads received: {metrics.get('total_leads_received', 0)}
- Rejected leads: {metrics.get('rejected_leads', 0)}
- Sold leads: {metrics.get('sold_leads', 0)}
- Unsold leads: {metrics.get('unsold_leads', 0)}
- Returned leads: {metrics.get('returned_leads', 0)}
- Gross revenue: ${metrics.get('gross_revenue', 0):.2f}
- Refunds: ${metrics.get('refunds', 0):.2f}
- Net revenue: ${metrics.get('net_revenue', 0):.2f}
- Top buyer by spend: {metrics.get('top_buyer_by_spend', 'N/A')}
- Buyers with low balance: {metrics.get('buyers_with_low_balance', [])}
- Buyers with cap reached: {metrics.get('buyers_with_cap_reached', [])}
- Top rejection reasons: {metrics.get('top_rejection_reasons', [])}
- Average routing latency: {metrics.get('average_routing_latency_ms', 0):.0f}ms

Be concise and actionable. Do not invent data beyond what is provided."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.3,
    )
    return response.choices[0].message.content
