from html import escape

from app.services.email_sender import send_html_email


def _text(value: object, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _recipient_groups(recipients: list[dict[str, object]]) -> dict[str, list[dict[str, str]]]:
    groups = {"to": [], "cc": [], "bcc": []}
    for recipient in recipients:
        recipient_type = str(recipient.get("recipient_type") or "to")
        if recipient_type not in groups:
            recipient_type = "to"
        email = str(recipient.get("email") or "").strip()
        if not email:
            continue
        groups[recipient_type].append(
            {
                "email": email,
                "name": str(recipient.get("display_name") or email),
            }
        )
    return groups


def _signal_rows(signals: list[dict[str, object]]) -> str:
    if not signals:
        return """
          <tr>
            <td colspan="5" style="padding: 14px; color: #6b7280; border-top: 1px solid #e5e7eb;">
              No report signals were found for this campaign and business date.
            </td>
          </tr>
        """

    rows = []
    for signal in signals[:12]:
        rows.append(
            f"""
            <tr>
              <td style="padding: 10px; border-top: 1px solid #e5e7eb;">{escape(_text(signal.get("headline")))}</td>
              <td style="padding: 10px; border-top: 1px solid #e5e7eb;">{escape(_text(signal.get("chain")))}</td>
              <td style="padding: 10px; border-top: 1px solid #e5e7eb;">{escape(_text(signal.get("brand")))}</td>
              <td style="padding: 10px; border-top: 1px solid #e5e7eb;">{escape(_text(signal.get("severity")))}</td>
              <td style="padding: 10px; border-top: 1px solid #e5e7eb;">{escape(_text(signal.get("recommended_action")))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _highlight_cards(highlights: list[dict[str, object]]) -> str:
    if not highlights:
        return """
          <div style="padding: 14px; color: #6b7280; border: 1px solid #e5e7eb; border-radius: 6px;">
            No priority highlights were selected for this campaign and business date.
          </div>
        """

    cards = []
    for highlight in highlights:
        severity = str(highlight.get("severity") or "").lower()
        border = "#dc2626" if severity in {"critical", "high"} else "#b45309" if severity == "medium" else "#15803d"
        background = "#fef2f2" if severity in {"critical", "high"} else "#fff7ed" if severity == "medium" else "#f0fdf4"
        cards.append(
            f"""
            <div style="margin-bottom: 10px; padding: 12px 14px; border-left: 4px solid {border}; background: {background}; border-radius: 6px;">
              <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em;">{escape(_text(highlight.get("family_label")))}</div>
              <div style="margin-top: 4px; font-size: 15px; font-weight: 700; color: #111827;">{escape(_text(highlight.get("headline")))}</div>
              <div style="margin-top: 4px; font-size: 13px; color: #374151;">{escape(_text(highlight.get("summary"), _text(highlight.get("business_reading"), "")))}</div>
              <div style="margin-top: 8px; font-size: 12px; color: #4b5563;">
                {escape(_text(highlight.get("chain")))} · {escape(_text(highlight.get("brand")))} · {escape(_text(highlight.get("severity")))}
              </div>
            </div>
            """
        )
    return "\n".join(cards)


def build_campaign_daily_report_email(
    *,
    campaign: dict[str, object],
    preview: dict[str, object],
) -> tuple[str, str, str]:
    business_date = _text(preview.get("business_date"))
    campaign_name = _text(campaign.get("name"), "Campaign")
    kpis = preview.get("kpis") if isinstance(preview.get("kpis"), dict) else {}
    signals = preview.get("records") if isinstance(preview.get("records"), list) else []
    highlights = preview.get("highlights") if isinstance(preview.get("highlights"), list) else []

    subject = f"Market Watch report - {campaign_name} - {business_date}"
    text_body = (
        f"Market Watch report\n\n"
        f"Campaign: {campaign_name}\n"
        f"Business date: {business_date}\n"
        f"Total signals: {kpis.get('total_signals', 0)}\n"
        f"High severity: {kpis.get('high_severity_signals', 0)}\n"
        f"Price signals: {kpis.get('price_signals', 0)}\n"
        f"Promo signals: {kpis.get('promo_signals', 0)}\n"
        f"Availability signals: {kpis.get('availability_signals', 0)}\n"
    )
    html_body = f"""
    <html>
      <body style="margin: 0; padding: 0; background: #f6f7f9; color: #111827; font-family: Arial, sans-serif;">
        <div style="max-width: 920px; margin: 0 auto; padding: 24px;">
          <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
            <div style="padding: 20px 24px; border-bottom: 3px solid #0c1f3d;">
              <div style="font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: .08em;">Market Watch</div>
              <h1 style="margin: 6px 0 0; font-size: 22px; line-height: 1.25; color: #0c1f3d;">{escape(campaign_name)}</h1>
              <div style="margin-top: 4px; font-size: 14px; color: #6b7280;">Daily report for {escape(business_date)}</div>
            </div>
            <div style="padding: 18px 24px;">
              <table role="presentation" style="width: 100%; border-collapse: collapse; margin-bottom: 18px;">
                <tr>
                  <td style="padding: 12px; background: #eef2ff; border-radius: 6px;"><strong>{int(kpis.get('total_signals') or 0)}</strong><br><span style="font-size: 12px; color: #6b7280;">Total signals</span></td>
                  <td style="padding: 12px; background: #fef2f2; border-radius: 6px;"><strong>{int(kpis.get('high_severity_signals') or 0)}</strong><br><span style="font-size: 12px; color: #6b7280;">High severity</span></td>
                  <td style="padding: 12px; background: #ecfdf5; border-radius: 6px;"><strong>{int(kpis.get('price_signals') or 0)}</strong><br><span style="font-size: 12px; color: #6b7280;">Price signals</span></td>
                  <td style="padding: 12px; background: #fff7ed; border-radius: 6px;"><strong>{int(kpis.get('promo_signals') or 0)}</strong><br><span style="font-size: 12px; color: #6b7280;">Promo signals</span></td>
                </tr>
              </table>
              <div style="margin: 6px 0 18px;">
                <div style="margin-bottom: 10px; font-size: 13px; font-weight: 700; color: #0c1f3d; text-transform: uppercase; letter-spacing: .06em;">
                  What needs attention today
                </div>
                {_highlight_cards([row for row in highlights if isinstance(row, dict)])}
              </div>
              <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                  <tr style="text-align: left; color: #6b7280;">
                    <th style="padding: 10px;">Signal</th>
                    <th style="padding: 10px;">Chain</th>
                    <th style="padding: 10px;">Brand</th>
                    <th style="padding: 10px;">Severity</th>
                    <th style="padding: 10px;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {_signal_rows([row for row in signals if isinstance(row, dict)])}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
    return subject, text_body, html_body


def send_campaign_daily_report_email(
    *,
    campaign: dict[str, object],
    preview: dict[str, object],
    recipients: list[dict[str, object]],
) -> tuple[str, list[dict[str, str]]]:
    groups = _recipient_groups(recipients)
    if not groups["to"] and (groups["cc"] or groups["bcc"]):
        groups["to"] = groups["cc"]
        groups["cc"] = []

    subject, text_body, html_body = build_campaign_daily_report_email(campaign=campaign, preview=preview)
    send_html_email(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        to=groups["to"],
        cc=groups["cc"],
        bcc=groups["bcc"],
    )
    return subject, [*groups["to"], *groups["cc"], *groups["bcc"]]
