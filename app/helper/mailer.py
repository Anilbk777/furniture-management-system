"""Email sending through Resend's HTTP API (async, no extra SDK needed)."""

import httpx

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

RESEND_URL = "https://api.resend.com/emails"

async def send_email(to: str, subject: str, html: str) -> None:
    """Sends one email. Raises httpx.HTTPError on failure."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}"
            },
            json={
                "from": settings.sender_email,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
    response.raise_for_status()

def _logo_block() -> str:
    url = settings.brand_logo_url.strip()
    if url:
        return (
            f'<img src="{url}" width="200" height="113" alt="Furniva" '
            'style="display:block;margin:0 auto 20px;border:0;outline:none;'
            'max-width:200px;height:auto;">'
        )
    return (
        '<span style="display:block;margin:0 auto 20px;font-size:24px;'
        'font-weight:700;color:#843E16;letter-spacing:-0.5px;">Furniva</span>'
    )

async def send_otp_email(to: str, code: str) -> None:
    """Meant for BackgroundTasks: logs failures instead of raising, never logs the code."""

    # HTML template with Furniva styling inspired by image_0.png
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify your email - Furniva</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #292524; /* Dark neutral background */
                font-family: 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                -webkit-font-smoothing: antialiased;
            }}
            .email-wrapper {{
                width: 100%;
                background-color: #292524;
                padding: 40px 0;
            }}
            .email-container {{
                max-width: 500px;
                margin: 0 auto;
                background-color: #F7F4F2; /* Warm light cream */
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }}
            .email-content {{
                padding: 40px 32px 32px 32px;
                text-align: center;
            }}
            
            h1 {{
                font-size: 28px;
                color: #292524;
                margin: 0 0 16px 0;
                font-weight: 600;
                letter-spacing: -0.5px;
            }}
            p {{
                font-size: 15px;
                line-height: 1.6;
                color: #4A4543;
                margin: 0 0 24px 0;
            }}
            .code-box {{
                background-color: #FFFFFF;
                border: 1px solid #E6DFDA;
                border-radius: 12px;
                padding: 20px;
                margin: 24px 0;
                letter-spacing: 6px;
                font-size: 32px;
                font-weight: 700;
                color: #843E16; /* Primary deep brown */
                display: inline-block;
                width: 80%;
                box-sizing: border-box;
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.02);
            }}
            .btn {{
                display: inline-block;
                background-color: #843E16; /* Primary */
                color: #FFFFFF !important;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                margin-top: 16px;
                transition: background-color 0.2s ease;
            }}
            /* Colored branding divider bar */
            .divider {{
                height: 4px;
                width: 100%;
                background: linear-gradient(90deg, #1E4B33 40%, #D97706 40%); /* Forest Green & Warm Gold */
            }}
            .email-footer {{
                background-color: #F7F4F2;
                padding: 24px 32px;
                text-align: center;
                border-top: 1px solid #E6DFDA;
            }}
            .footer-tagline {{
                font-size: 14px;
                font-weight: 500;
                color: #4A4543;
                margin: 0 0 12px 0;
            }}
            .footer-icons {{
                margin-bottom: 12px;
            }}
            .footer-icon {{
                display: inline-block;
                margin: 0 6px;
                color: #843E16;
                text-decoration: none;
                font-size: 16px;
            }}
            .footer-legal {{
                font-size: 11px;
                color: #8C8480;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="email-container">
                <div class="email-content">
                    {_logo_block()}
                    
                    <h1>Verify your email</h1>
                    <p>To finish setting up your Furniva account, please use the verification code below. It will expire in 10 minutes.</p>
                    
                    <div class="code-box">{code}</div>
                    
                    <p style="font-size: 14px; color: #736B67; margin-bottom: 8px;">
                        If you didn't request this, you can safely ignore this email.
                    </p>
                    
                    <a href="{settings.frontend_url.rstrip('/')}" class="btn">Go to Furniva</a>
                </div>
                
                <div class="divider"></div>
                
                <div class="email-footer">
                    <p class="footer-tagline">Furniva — Crafted for your home</p>
                    <div class="footer-icons">
                        <span style="color: #843E16; font-size: 16px;">✦</span>
                        <span style="color: #D97706; font-size: 16px;">✦</span>
                        <span style="color: #1E4B33; font-size: 16px;">✦</span>
                    </div>
                    <p class="footer-legal">© 2026 Furniva Inc. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    try:
        await send_email(to, f"{code} is your Furniva verification code", html)
        logger.info(f"OTP email sent to {to}")
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"Resend rejected OTP email to {to}: {exc.response.status_code} {exc.response.text}"
        )
    except httpx.HTTPError as exc:
        logger.error(f"OTP email to {to} failed: {exc!r}")


async def send_reset_password_email(to: str, token: str, mobile: bool = False) -> None:
    """Email with a 'Reset password' button. Safe for BackgroundTasks; never logs the token."""
    reset_url = (
        settings.mobile_reset_url
        if mobile and settings.mobile_reset_url
        else f"{settings.frontend_url.rstrip('/')}/reset-password"
    )
    link = f"{reset_url}?token={token}"
    # HTML template with Furniva styling inspired by your brand palette
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reset your password - Furniva</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #292524; /* Dark neutral background */
                font-family: 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                -webkit-font-smoothing: antialiased;
            }}
            .email-wrapper {{
                width: 100%;
                background-color: #292524;
                padding: 40px 0;
            }}
            .email-container {{
                max-width: 500px;
                margin: 0 auto;
                background-color: #F7F4F2; /* Warm light cream */
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }}
            .email-content {{
                padding: 40px 32px 32px 32px;
                text-align: center;
            }}
            
            h1 {{
                font-size: 28px;
                color: #292524;
                margin: 0 0 16px 0;
                font-weight: 600;
                letter-spacing: -0.5px;
            }}
            p {{
                font-size: 15px;
                line-height: 1.6;
                color: #4A4543;
                margin: 0 0 24px 0;
            }}
            .btn {{
                display: inline-block;
                background-color: #843E16; /* Primary deep brown */
                color: #FFFFFF !important;
                text-decoration: none;
                padding: 14px 28px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                margin: 8px 0 24px 0;
                box-shadow: 0 2px 4px rgba(132, 62, 22, 0.2);
            }}
            .fallback-box {{
                background-color: #FFFFFF;
                border: 1px solid #E6DFDA;
                border-radius: 8px;
                padding: 16px;
                margin: 20px 0;
                text-align: left;
                word-break: break-all;
            }}
            .fallback-text {{
                font-size: 12px;
                color: #736B67;
                margin: 0 0 6px 0;
            }}
            .fallback-link {{
                font-size: 12px;
                color: #843E16;
                text-decoration: underline;
            }}
            /* Colored branding divider bar */
            .divider {{
                height: 4px;
                width: 100%;
                background: linear-gradient(90deg, #1E4B33 40%, #D97706 40%); /* Forest Green & Warm Gold */
            }}
            .email-footer {{
                background-color: #F7F4F2;
                padding: 24px 32px;
                text-align: center;
                border-top: 1px solid #E6DFDA;
            }}
            .footer-tagline {{
                font-size: 14px;
                font-weight: 500;
                color: #4A4543;
                margin: 0 0 12px 0;
            }}
            .footer-icons {{
                margin-bottom: 12px;
            }}
            .footer-legal {{
                font-size: 11px;
                color: #8C8480;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="email-container">
                <div class="email-content">
                    {_logo_block()}
                    <h1>Reset your password</h1>
                    <p>We received a request to reset the password for your Furniva account. Click the button below to choose a new one. This link expires in 1 hour.</p>
                    
                    <a href="{link}" class="btn">Reset password</a>
                    
                    <div class="fallback-box">
                        <p class="fallback-text">If the button doesn't work, copy and paste this link into your browser:</p>
                        <a href="{link}" class="fallback-link">{link}</a>
                    </div>
                    
                    <p style="font-size: 13px; color: #736B67; margin-top: 24px; margin-bottom: 0;">
                        If you didn't request this, you can safely ignore this email. Your password will remain unchanged.
                    </p>
                </div>
                
                <div class="divider"></div>
                
                <div class="email-footer">
                    <p class="footer-tagline">Furniva — Crafted for your home</p>
                    <div class="footer-icons">
                        <span style="color: #843E16; font-size: 16px;">✦</span>
                        <span style="color: #D97706; font-size: 16px;">✦</span>
                        <span style="color: #1E4B33; font-size: 16px;">✦</span>
                    </div>
                    <p class="footer-legal">© 2026 Furniva Inc. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        await send_email(to, "Reset your Furniva password", html)
        logger.info(f"Password reset email sent to {to}")
    except httpx.HTTPStatusError as exc:
        logger.error(f"Resend rejected reset email to {to}: {exc.response.status_code} {exc.response.text}")
    except httpx.HTTPError as exc:
        logger.error(f"Reset email to {to} failed: {exc!r}")