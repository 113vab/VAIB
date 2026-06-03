import uuid
import time
import logging
from typing import Callable, Dict, Any, List

logger = logging.getLogger("vaib")

class PermissionsManager:
    """
    Manages security permissions for critical system actions.
    Restricted actions are registered and held in a pending state until approved via the API.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PermissionsManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._pending_actions = {}
        return cls._instance

    def request_permission(self, action_type: str, details: Dict[str, Any], callback: Callable[[], Any]) -> Dict[str, Any]:
        """
        Request permission to run a restricted action.
        Generates a unique action_id and caches the request.
        """
        action_id = str(uuid.uuid4())
        record = {
            "id": action_id,
            "type": action_type,
            "details": details,
            "callback": callback,
            "status": "pending",
            "timestamp": time.time(),
            "result": None,
            "error": None
        }
        self._pending_actions[action_id] = record
        logger.info(f"Permission requested: {action_type} (ID: {action_id})")
        return {
            "status": "pending_approval",
            "action_id": action_id,
            "type": action_type,
            "message": f"This action ({action_type}) requires your confirmation, Sir."
        }

    def get_pending_actions(self) -> List[Dict[str, Any]]:
        """List all currently pending actions (omitting the callback function from serialization)."""
        pending = []
        for action_id, record in self._pending_actions.items():
            if record["status"] == "pending":
                pending.append({
                    "id": record["id"],
                    "type": record["type"],
                    "details": record["details"],
                    "status": record["status"],
                    "timestamp": record["timestamp"]
                })
        return pending

    def get_action_status(self, action_id: str) -> Dict[str, Any]:
        """Get the details and status of a specific action by ID."""
        record = self._pending_actions.get(action_id)
        if not record:
            return {"status": "not_found"}
        return {
            "id": record["id"],
            "type": record["type"],
            "details": record["details"],
            "status": record["status"],
            "result": record["result"],
            "error": record["error"]
        }

    def approve_action(self, action_id: str) -> Dict[str, Any]:
        """Approve and execute a pending action."""
        record = self._pending_actions.get(action_id)
        if not record:
            return {"status": "error", "message": f"Action ID {action_id} not found."}
        
        if record["status"] != "pending":
            return {"status": "error", "message": f"Action is already in '{record['status']}' state."}
        
        logger.info(f"Action {action_id} approved. Executing callback...")
        try:
            record["status"] = "executing"
            result = record["callback"]()
            record["status"] = "approved"
            record["result"] = result
            logger.info(f"Action {action_id} executed successfully. Result: {result}")
            return {"status": "success", "result": result}
        except Exception as e:
            record["status"] = "failed"
            record["error"] = str(e)
            logger.error(f"Failed to execute action {action_id}: {e}")
            return {"status": "failed", "error": str(e)}

    def deny_action(self, action_id: str) -> Dict[str, Any]:
        """Deny a pending action."""
        record = self._pending_actions.get(action_id)
        if not record:
            return {"status": "error", "message": f"Action ID {action_id} not found."}
        
        if record["status"] != "pending":
            return {"status": "error", "message": f"Action is already in '{record['status']}' state."}
        
        record["status"] = "denied"
        logger.info(f"Action {action_id} was denied by the user.")
        return {"status": "success", "message": "Action denied."}

    def clear_all(self):
        """Clear all registered actions. Mostly for testing."""
        self._pending_actions.clear()
