import requests
from msal import ConfidentialClientApplication


TENANT_ID = "TU_ID"
CLIENT_ID = "TU_ID"
CLIENT_SECRET = "TU_SECRE"



def get_token():

    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )


    result = app.acquire_token_for_client(
        scopes=[
            "https://graph.microsoft.com/.default"
        ]
    )


    return result["access_token"]



def get_site():

    token = get_token()


    headers = {
        "Authorization": f"Bearer {token}"
    }


    url = (
        "https://graph.microsoft.com/v1.0"
        "/sites/bymyself0.sharepoint.com:/sites/Rummi"
    )


    r = requests.get(
        url,
        headers=headers
    )


    print(r.status_code)

    print(r.json())


get_site()