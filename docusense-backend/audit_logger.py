"""
Audit Logging Module
Generates audit logs from application events and Azure Monitor data
"""
import csv
import io
from typing import Dict, Any, List
from datetime import datetime, timedelta
import random

class AuditLogger:
    def __init__(self):
        # In production, this would connect to Azure Monitor/Log Analytics
        # self.logs_client = LogsQueryClient(credential=DefaultAzureCredential())
        pass
    
    def generate_audit_csv(self, from_date: str, to_date: str, tenant_id: str = "default") -> str:
        """Generate audit log CSV for the specified date range"""
        
        # Parse date strings
        start_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Get audit events
        events = self._get_audit_events(start_date, end_date, tenant_id)
        
        # Generate CSV
        return self._events_to_csv(events)
    
    def _get_audit_events(self, start_date: datetime, end_date: datetime, tenant_id: str) -> List[Dict[str, Any]]:
        """Get audit events for the specified period"""
        
        # For now, generate realistic sample data
        # In production, this would query Azure Monitor/Log Analytics
        
        events = []
        current_date = start_date
        
        while current_date <= end_date:
            # Generate 1-5 events per day
            daily_events = random.randint(1, 5)
            
            for _ in range(daily_events):
                event_time = current_date + timedelta(
                    hours=random.randint(8, 18),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59)
                )
                
                event = self._generate_sample_event(event_time, tenant_id)
                events.append(event)
            
            current_date += timedelta(days=1)
        
        # Sort events by timestamp
        events.sort(key=lambda x: x['timestamp'])
        
        return events
    
    def _generate_sample_event(self, timestamp: datetime, tenant_id: str) -> Dict[str, Any]:
        """Generate a realistic sample audit event"""
        
        event_types = [
            ("search", "User performed search query", 0.4),
            ("document_ingestion", "Document ingested from OneDrive/SharePoint", 0.2),
            ("authentication", "User authentication event", 0.15),
            ("admin_settings", "Admin configuration change", 0.05),
            ("webhook_event", "Webhook notification received", 0.1),
            ("error", "System error occurred", 0.05),
            ("file_upload", "File uploaded to SharePoint", 0.05)
        ]
        
        # Weighted random selection
        rand = random.random()
        cumulative = 0
        for event_type, description, weight in event_types:
            cumulative += weight
            if rand <= cumulative:
                break
        
        # Generate event details based on type
        if event_type == "search":
            user = self._random_user()
            query = self._random_search_query()
            details = f'Query: "{query}", Results: {random.randint(0, 15)}'
            result = "success"
            
        elif event_type == "document_ingestion":
            user = "system"
            filename = self._random_filename()
            details = f'File: "{filename}", Size: {random.randint(50, 5000)}KB'
            result = "success" if random.random() > 0.1 else "failed"
            
        elif event_type == "authentication":
            user = self._random_user()
            auth_method = random.choice(["Teams SSO", "Browser login", "API token"])
            details = f'Method: {auth_method}, IP: {self._random_ip()}'
            result = "success" if random.random() > 0.05 else "failed"
            
        elif event_type == "admin_settings":
            user = self._random_admin_user()
            setting = random.choice(["region", "retention_days", "webhook_config"])
            old_value = random.choice(["eastus", "90", "enabled"])
            new_value = random.choice(["westeurope", "30", "disabled"])
            details = f'Setting: {setting}, Changed from "{old_value}" to "{new_value}"'
            result = "success"
            
        elif event_type == "webhook_event":
            user = "system"
            change_type = random.choice(["created", "updated", "deleted"])
            resource = random.choice(["/me/drive/root", "/sites/root/drives/abc123"])
            details = f'Change: {change_type}, Resource: {resource}'
            result = "success" if random.random() > 0.1 else "failed"
            
        elif event_type == "error":
            user = self._random_user()
            error_type = random.choice(["search_timeout", "auth_failure", "index_error"])
            details = f'Error: {error_type}, Code: {random.randint(400, 599)}'
            result = "error"
            
        else:  # file_upload
            user = self._random_user()
            filename = self._random_filename()
            details = f'Uploaded: "{filename}" to SharePoint'
            result = "success"
        
        return {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "user": user,
            "details": details,
            "result": result,
            "tenant_id": tenant_id,
            "session_id": f"sess_{random.randint(100000, 999999)}"
        }
    
    def _random_user(self) -> str:
        """Generate random user email"""
        first_names = ["john", "jane", "bob", "alice", "charlie", "diana", "frank", "grace"]
        last_names = ["smith", "johnson", "brown", "davis", "wilson", "moore", "taylor", "anderson"]
        domains = ["contoso.com", "fabrikam.com", "adventure-works.com"]
        
        first = random.choice(first_names)
        last = random.choice(last_names)
        domain = random.choice(domains)
        
        return f"{first}.{last}@{domain}"
    
    def _random_admin_user(self) -> str:
        """Generate random admin user email"""
        admin_users = [
            "admin@contoso.com",
            "it.admin@fabrikam.com", 
            "system.admin@adventure-works.com",
            "tenant.admin@contoso.com"
        ]
        return random.choice(admin_users)
    
    def _random_search_query(self) -> str:
        """Generate random search query"""
        queries = [
            "quarterly financial report",
            "teams integration guide",
            "employee handbook",
            "project timeline",
            "budget proposal",
            "meeting notes",
            "technical documentation",
            "policy updates",
            "training materials",
            "customer feedback"
        ]
        return random.choice(queries)
    
    def _random_filename(self) -> str:
        """Generate random filename"""
        names = ["report", "document", "presentation", "spreadsheet", "memo", "proposal", "guide", "manual"]
        extensions = [".docx", ".xlsx", ".pptx", ".pdf", ".txt"]
        
        name = random.choice(names)
        number = random.randint(1, 100)
        ext = random.choice(extensions)
        
        return f"{name}_{number}{ext}"
    
    def _random_ip(self) -> str:
        """Generate random IP address"""
        return f"{random.randint(192, 203)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
    
    def _events_to_csv(self, events: List[Dict[str, Any]]) -> str:
        """Convert events list to CSV string"""
        if not events:
            return "timestamp,event_type,user,details,result\n"
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["timestamp", "event_type", "user", "details", "result", "tenant_id", "session_id"])
        
        # Write events
        for event in events:
            writer.writerow([
                event["timestamp"],
                event["event_type"],
                event["user"],
                event["details"],
                event["result"],
                event["tenant_id"],
                event["session_id"]
            ])
        
        return output.getvalue()
    
    def _query_log_analytics(self, start_date: datetime, end_date: datetime, tenant_id: str) -> List[Dict[str, Any]]:
        """Query Log Analytics for audit events (production implementation)"""
        # This would be the production implementation
        """
        query = '''
        union traces, exceptions, requests
        | where timestamp between (datetime({start}) .. datetime({end}))
        | where customDimensions.tenantId == "{tenant_id}"
        | project 
            timestamp,
            event_type = case(
                itemType == "trace", "system_event",
                itemType == "exception", "error", 
                itemType == "request", "api_request",
                "unknown"
            ),
            user = tostring(customDimensions.userId),
            details = message,
            result = case(success == true, "success", "failed")
        | order by timestamp desc
        '''.format(start=start_date.isoformat(), end=end_date.isoformat(), tenant_id=tenant_id)
        
        result = self.logs_client.query_workspace(
            workspace_id=os.getenv("LOG_ANALYTICS_WORKSPACE_ID"),
            query=query,
            timespan=(end_date - start_date)
        )
        
        return self._parse_log_analytics_result(result)
        """
        pass

# Global instance
audit_logger = AuditLogger()

def generate_audit_csv(from_date: str, to_date: str, tenant_id: str = "default") -> str:
    """Generate audit log CSV"""
    return audit_logger.generate_audit_csv(from_date, to_date, tenant_id) 