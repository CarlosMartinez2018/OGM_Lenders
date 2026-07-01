"""
Test de conexion a SharePoint via Microsoft Graph API.

URL objetivo (desofuscada de proofpoint):
  https://finesa.sharepoint.com/sites/AndexInsurance/LenderInsurance Repository/Forms/AllItems.aspx

IMPORTANTE: el tenant del sitio (finesa.sharepoint.com) es DISTINTO al tenant
configurado en AZURE_TENANT_ID (acentopartners). Para que esto funcione, el
admin de Finesa debe haber autorizado tu app y otorgado el permiso
'Sites.Read.All' (o 'Sites.Selected') como Application Permission.
"""
import os
import urllib.parse
import msal
import httpx
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

# Hostname y ruta del site (parametrizable por env, con defaults de Finesa)
SP_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "finesa.sharepoint.com")
SP_SITE_PATH = os.getenv("SHAREPOINT_SITE_PATH", "/sites/AndexInsurance")
SP_LIBRARY = os.getenv("SHAREPOINT_LIBRARY", "LenderInsurance Repository")

if not TENANT_ID or not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Credenciales de Azure no encontradas en el archivo .env")
    exit(1)

authority = f"https://login.microsoftonline.com/{TENANT_ID}"
scopes = ["https://graph.microsoft.com/.default"]

app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET
)

print(f"1. Buscando Token de Seguridad de Microsoft para el Tenant: {TENANT_ID}...")
result = app.acquire_token_silent(scopes, account=None)
if not result:
    result = app.acquire_token_for_client(scopes=scopes)

if "access_token" not in result:
    print("X ERROR FATAL: No se pudo obtener el token inicial de Microsoft.")
    print(result.get("error"))
    print(result.get("error_description"))
    exit(1)

print("EXITO: Token obtenido con exito de Azure AD.")
access_token = result["access_token"]

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}

# ----------------------------------------------------------------------------
# Paso 2: Resolver el ID del site por hostname + path
# ----------------------------------------------------------------------------
site_url = f"https://graph.microsoft.com/v1.0/sites/{SP_HOSTNAME}:{SP_SITE_PATH}"
print(f"\n2. Resolviendo el site de SharePoint: {SP_HOSTNAME}{SP_SITE_PATH}")
print(f"   GET {site_url}")

try:
    response = httpx.get(site_url, headers=headers, timeout=30.0)
except Exception as e:
    print(f"X Error al intentar hacer la peticion HTTP: {e}")
    exit(1)

if response.status_code != 200:
    print(f"ERROR AL RESOLVER EL SITE. (Codigo {response.status_code})")
    print(f"Detalle: {response.text}")
    if response.status_code == 401:
        print("\nNOTA: 401 Unauthorized. El token es valido pero no autoriza este recurso.")
        print("Verifica que el admin del tenant de Finesa haya consentido la app y")
        print("otorgado 'Sites.Read.All' o 'Sites.Selected' como Application Permission.")
    elif response.status_code == 403:
        print("\nNOTA: 403 Forbidden. La app fue reconocida pero no tiene permisos sobre")
        print("este site. En el Portal de Azure -> API Permissions, agrega")
        print("'Sites.Read.All' (Application) y solicita 'Grant Admin Consent' al admin")
        print(f"del tenant duenio de {SP_HOSTNAME}.")
    elif response.status_code == 404:
        print("\nNOTA: 404 Not Found. El site no existe o tu app no es visible a el.")
        print("Esto es comun cuando los tenants son diferentes: tu app esta registrada en")
        print(f"el tenant {TENANT_ID} pero el site vive en otro tenant ({SP_HOSTNAME}).")
        print("Pide al admin de Finesa que registre/apruebe la app multi-tenant.")
    exit(1)

site_data = response.json()
site_id = site_data.get("id", "")
site_display = site_data.get("displayName", "(sin nombre)")
print(f"EXITO: Site encontrado. displayName='{site_display}'")
print(f"       site_id={site_id}")

# ----------------------------------------------------------------------------
# Paso 3: Listar las bibliotecas (drives) del site
# ----------------------------------------------------------------------------
drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
print(f"\n3. Listando bibliotecas (drives) del site...")
print(f"   GET {drives_url}")

response = httpx.get(drives_url, headers=headers, timeout=30.0)
if response.status_code != 200:
    print(f"ERROR AL LISTAR DRIVES. (Codigo {response.status_code})")
    print(f"Detalle: {response.text}")
    exit(1)

drives = response.json().get("value", [])
print(f"EXITO: {len(drives)} biblioteca(s) encontrada(s):")
for d in drives:
    print(f"  - {d.get('name')!r:50}  driveType={d.get('driveType')}  id={d.get('id')}")

# ----------------------------------------------------------------------------
# Paso 4: Encontrar la biblioteca objetivo y listar su raiz
# ----------------------------------------------------------------------------
target = next((d for d in drives if d.get("name") == SP_LIBRARY), None)
if not target:
    print(f"\nADVERTENCIA: No se encontro la biblioteca '{SP_LIBRARY}'.")
    print("Revisa el listado anterior y ajusta SHAREPOINT_LIBRARY en .env si hace falta.")
    exit(0)

drive_id = target["id"]
root_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children?$top=10"
print(f"\n4. Listando contenido raiz de '{SP_LIBRARY}' (max 10)...")
print(f"   GET {root_url}")

response = httpx.get(root_url, headers=headers, timeout=30.0)
if response.status_code != 200:
    print(f"ERROR AL LISTAR CONTENIDO. (Codigo {response.status_code})")
    print(f"Detalle: {response.text}")
    exit(1)

items = response.json().get("value", [])
print(f"EXITO: Conexion perfecta. {len(items)} item(s) en la raiz:")
for it in items:
    kind = "DIR " if "folder" in it else "FILE"
    size = it.get("size", 0)
    print(f"  [{kind}] {it.get('name')!r}  size={size}")
