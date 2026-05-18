from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests

app = FastAPI()

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class PriorAuthRequest(BaseModel):

    SDMemberID: str
    SDFamilyID: str
    SDAge: int
    SDFamilyMemberRelationType: str

    SDFirstName: Optional[str] = None
    SDLastName: Optional[str] = None

    SDContactReasonCode: Optional[str] = None
    SDEventDisplayID: Optional[str] = None

    SDServiceModel: Optional[str] = None
    SDPolicyNumber: Optional[str] = None

    address: Optional[str] = None
    SDPrimaryContactNumber: Optional[str] = None

    SDOkToSMS: bool = False
    SDOkToEmail: bool = False


@app.get("/")
def root():
    return {
        "status": "API RUNNING"
    }


@app.get("/health")
def health():
    return {
        "status": "HEALTHY"
    }


@app.post("/prior-auth-denial")
def prior_auth_denial(
    request: PriorAuthRequest,
    x_api_key: str = Header(...)
):

    if x_api_key != "BRD_PRIOR_AUTH_2026":
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    is_minor = (
    request.SDAge >= 0 and
    request.SDAge <= 11 and
    request.SDFamilyMemberRelationType in [
        "Subscriber of Child",
        "Child"
    ]
    )

    # ---------------------------------------
    # Dynamic Prompt Creation
    # ---------------------------------------

    if is_minor:

        audience_type = "minor dependent member"

        communication_context = """
        The member is a child dependent.
        Communication must be redirected to the subscriber/parent.
        Inform them that prior authorization was denied.
        Inform them that a nurse will contact them shortly.
        Encourage them to answer the nurse call for guidance.
        Keep message empathetic and professional.
        """

    else:

        audience_type = "adult member"

        communication_context = """
        Inform the member that prior authorization was denied.
        Inform them that a nurse will contact them shortly.
        Encourage them to answer the nurse call for guidance.
        Keep message professional and supportive.
        """

    # ---------------------------------------
    # AI Prompt
    # ---------------------------------------

    system_prompt = f"""
    You are an AJO healthcare communication assistant.

    Generate:
    
    1. SMS text Content
    2. Professional Email Subject
    3. Professional Email Body

    Context:
    {communication_context}

    Rules:
    - Healthcare tone
    - Human sounding
    - Do not mention AI
    - Keep SMS under 250 characters
    - Email should be concise
    - Mention nurse outreach
    - Mention prior authorization denial
    - Email Should Include:
        - Header
        - Footer
        - Clean HTML
    """

    user_prompt = f"""
    Member Name: {request.SDFirstName} {request.SDLastName}
    Policy Number: {request.SDPolicyNumber}
    Service Model: {request.SDServiceModel}
    Contact Reason: {request.SDContactReasonCode}
    Audience Type: {audience_type}
    """

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.4,
        "max_tokens": 700
    }

    response = requests.post(
        GROQ_URL,
        headers=headers,
        json=payload
    )

    # 1. Print the response status and content directly to your terminal
    print(f"--- DEBUG: Groq Status Code: {response.status_code} ---")
    print(f"--- DEBUG: Groq Error Body: {response.text} ---")

    # 2. Prevent the application from crashing with a generic 500 error
    if response.status_code != 200:
        raise HTTPException(
            status_code=200,
            detail=f"Groq API Error: {response.text}"
        )

    ai_result = response.json()
    generated_message = ai_result["choices"][0]["message"]["content"]


    # ---------------------------------------
    # FINAL RESPONSE TO AJO
    # ---------------------------------------

    return {

        "journeyType":
        "DEPENDENT_JOURNEY" if is_minor else "ADULT_MEMBER_JOURNEY",

        "eventName":
        "Subscriber on Behalf of Child Event"
        if is_minor else
        "Adult Member Prior Auth Event",

        "memberId":
        request.SDMemberID,

        "familyId":
        request.SDFamilyID,

        "emailToUse":
        request.address,

        "phoneToUse":
        request.SDPrimaryContactNumber,

        "sendSMS":
        request.SDOkToSMS,

        "sendEmail":
        request.SDOkToEmail,

        "generatedCommunication":
        generated_message
    }
