"""Safe, reusable notification email templates."""

import html
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailCategoryTemplate:
    label: str
    portal_path: str


CATEGORY_TEMPLATES = {
    "HOMEWORK": EmailCategoryTemplate("Homework update", "/parent/homework"),
    "ATTENDANCE": EmailCategoryTemplate("Attendance update", "/parent/attendance"),
    "EXAM_SCHEDULE": EmailCategoryTemplate("Exam schedule", "/parent/exams"),
    "RESULTS": EmailCategoryTemplate("Results update", "/parent/results"),
    "CIRCULAR": EmailCategoryTemplate("School circular", "/parent/circulars"),
    "EVENT": EmailCategoryTemplate("School event", "/parent/calendar"),
    "ADMIN_ANNOUNCEMENT": EmailCategoryTemplate("School announcement", "/parent/dashboard"),
    "GENERAL": EmailCategoryTemplate("Parent notification", "/parent/dashboard"),
    "FEE_REMINDER": EmailCategoryTemplate("Fee reminder", "/parent/fees"),
    "FEE_PAYMENT": EmailCategoryTemplate("Fee payment update", "/parent/fees"),
    "ACCOUNT": EmailCategoryTemplate("Account update", "/parent/profile"),
    "EMAIL_VERIFICATION": EmailCategoryTemplate("Email verification", "/parent/profile"),
}


def get_category_template(category: str | None) -> EmailCategoryTemplate:
    return CATEGORY_TEMPLATES.get(
        (category or "GENERAL").strip().upper(), CATEGORY_TEMPLATES["GENERAL"]
    )


def render_notification_email_text(
    category: str,
    title: str,
    message: str,
    portal_url: str,
) -> str:
    template = get_category_template(category)
    destination = f"{portal_url.rstrip('/')}{template.portal_path}"
    return (
        f"Rosary Matriculation Higher Secondary School\n"
        f"{template.label}\n\n{title}\n\n{message}\n\n"
        f"Open the secure parent portal: {destination}\n\n"
        "This message was sent by Rosary School. Contact the school office "
        "if you need assistance."
    )


def render_notification_email_html(
    category: str,
    title: str,
    message: str,
    portal_url: str,
    unsubscribe_url: str | None = None,
) -> str:
    template = get_category_template(category)
    safe_title = html.escape(title)
    safe_message = "<br>".join(html.escape(message).splitlines())
    safe_label = html.escape(template.label)
    safe_portal_url = html.escape(
        f"{portal_url.rstrip('/')}{template.portal_path}", quote=True
    )
    safe_logo_url = html.escape(
        f"{portal_url.rstrip('/')}/logo/rosary-logo.png", quote=True
    )
    unsubscribe_html = ""
    if unsubscribe_url:
        safe_unsubscribe_url = html.escape(unsubscribe_url, quote=True)
        unsubscribe_html = (
            f'<br><a href="{safe_unsubscribe_url}" style="color:#475569">'
            "Unsubscribe from email notifications</a>"
        )
    return f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only"></head>
  <body style="margin:0;background:#f3f7fe;font-family:Arial,Helvetica,sans-serif;color:#10233f">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f3f7fe;padding:24px 12px"><tr><td align="center">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#fff;border:1px solid #cfe0f5;border-radius:16px;overflow:hidden">
        <tr><td style="background:#0b3a67;padding:22px 28px;color:#fff"><table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
          <td style="padding-right:14px;vertical-align:middle"><img src="{safe_logo_url}" width="52" height="52" alt="Rosary School" style="display:block;width:52px;height:52px;object-fit:contain;border:0"></td>
          <td style="vertical-align:middle;color:#fff"><div style="font-size:22px;font-weight:700">Rosary Matriculation Higher Secondary School</div><div style="font-size:12px;opacity:.85;margin-top:4px">{safe_label}</div></td>
        </tr></table></td></tr>
        <tr><td style="padding:30px 28px"><h1 style="font-size:22px;margin:0 0 18px">{safe_title}</h1><div style="font-size:15px;line-height:1.65">{safe_message}</div>
          <p style="margin:26px 0 0"><a href="{safe_portal_url}" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700">Open Parent Portal</a></p>
        </td></tr>
        <tr><td style="padding:16px 28px;background:#f8fafc;color:#64748b;font-size:12px">This message was sent by Rosary School. Please use the secure portal for student information and contact the school office if you need assistance.{unsubscribe_html}</td></tr>
      </table>
    </td></tr></table>
  </body>
</html>"""
