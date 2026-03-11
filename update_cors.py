import os
from google.cloud import storage
from google.oauth2 import service_account

def main():
    key_path = 'gcp-key.json'
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    client = storage.Client(credentials=creds)
    bucket = client.bucket('synthiot')
    
    # Update CORS
    bucket.cors = [{
        'origin': ['*'],
        'method': ['GET', 'OPTIONS'],
        'responseHeader': ['*'],
        'maxAgeSeconds': 3600
    }]
    bucket.patch()
    print('CORS updated successfully on bucket synthiot')

    # Make the specific problematic blob public
    blob = bucket.blob('synthetic_data_1cfd83a4b5314ef4b8441df11ca26005.csv')
    if blob.exists():
        blob.make_public()
        print('Blob made public successfully.')
    else:
        print('Blob not found.')

if __name__ == '__main__':
    main()
