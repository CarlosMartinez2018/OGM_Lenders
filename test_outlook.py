import os
import msal
import httpx
from dotenv import load_dotenv

# Cargar las credenciales automáticamente desde el archivo .env
load_dotenv()

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
MAILBOX = os.getenv("OUTLOOK_MAILBOX")

if not TENANT_ID or not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Credenciales de Azure no encontradas en el archivo .env")
    exit(1)

authority = f"https://login.microsoftonline.com/{TENANT_ID}"
# El scope predeterminado para Client Credentials
scopes = ["https://graph.microsoft.com/.default"]

app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET
)

print(f"1. Buscando Token de Seguridad de Microsoft para el Tenant: {TENANT_ID}...")
result = app.acquire_token_silent(scopes, account=None)
if not result:
    result = app.acquire_token_for_client(scopes=scopes)

if "access_token" in result:
    print("EXITO: Token obtenido con exito de Azure AD.")
    access_token = result["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Intentamos leer la bandeja de entrada del buzón objetivo
    url = f"https://graph.microsoft.com/v1.0/users/{MAILBOX}/mailFolders/Inbox/messages?$top=5"
    print(f"\n2. Probando Permisos de Lectura sobre el buzon: {MAILBOX}...")
    
    try:
        response = httpx.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"EXITO: Conexion perfecta. Se han detectado {len(data.get('value', []))} correos en la bandeja de entrada.")
        else:
            print(f"ERROR EN MICROSOFT GRAPH API. (Codigo {response.status_code})")
            print(f"Detalle del error: {response.text}")
            print("\nNOTA: Si el codigo es 403 Forbidden, recuerda que en el Portal de Azure debes ir a API Permissions, agregar 'Mail.Read' como 'Application Permission' y darle clic al boton 'Grant Admin Consent'.")
    except Exception as e:
         print(f"✗ Error al intentar hacer la petición HTTP: {e}")
         
else:
    print("✗ ERROR FATAL: No se pudo obtener el token inicial de Microsoft.")
    print(result.get("error"))
    print(result.get("error_description"))
