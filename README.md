# Microservices Overview

| Microservice | Description                                    |
|--------------|------------------------------------------------|
| <span style="color:#1E90FF;">**Images (Backup)**</span>  | Responsible for backing up image data, storing snapshots of image-related info securely. |
| <span style="color:#32CD32;">**Models (Backup)**</span>  | Handles backup of model data, ensuring versioned copies are safely stored.               |
| <span style="color:#FF8C00;">**Porders (Backup)**</span> | Extracts information from PostgreSQL and stores backup copies into MongoDB.              |
| <span style="color:#8A2BE2;">**Users (Backup)**</span>   | Backs up user data including profiles and credentials securely for recovery.             |
| <span style="color:#DC143C;">**Chat (Rollback)**</span>  | Manages rollback of chat data to previous states for recovery and error correction.      |
| <span style="color:#FF1493;">**Images (Rollback)**</span>| Handles rollback operations for image data, restoring previous versions when needed.    |
| <span style="color:#00CED1;">**Models (Rollback)**</span>| Performs rollback on model data, reverting to stable versions during errors or failures. |
| <span style="color:#FFD700;">**Porders (Rollback)**</span>| Responsible for rollback of PostgreSQL extracted data stored in MongoDB backups.         |
| <span style="color:#20B2AA;">**Users (Rollback)**</span> | Provides rollback features for user data, enabling restoration from backups.             |
| <span style="color:#FF4500;">**Additional Service**</span>| Placeholder for any other rollback or backup microservice in the system.                 |

---

*Each microservice ensures data integrity and availability either by backing up critical information or enabling rollback capabilities to recover from failures.*