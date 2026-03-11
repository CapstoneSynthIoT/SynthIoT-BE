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
    
    # Get current IAM policy
    policy = bucket.get_iam_policy(requested_policy_version=3)
    
    # Add allUsers to roles/storage.objectViewer
    policy.bindings.append(
        {"role": "roles/storage.objectViewer", "members": {"allUsers"}}
    )
    
    # Set the updated policy
    bucket.set_iam_policy(policy)
    print('IAM Policy updated successfully! The bucket synthiot is now public.')

if __name__ == '__main__':
    main()
