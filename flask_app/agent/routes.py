import logging

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)
agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")


@agent_bp.route("/execute", methods=["POST"])
def execute_agent():
    """Execute an agent tool/command via JSON API."""
    if not hasattr(g, "user") or not g.user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    prompt = data.get("prompt", "")
    tool_name = data.get("tool")
    payload = data.get("payload", {})

    try:
        from . import ToolPermissionContext, build_agent_runtime

        runtime = build_agent_runtime(
            user_id=g.user.id,
            permission_context=ToolPermissionContext(),
        )

        if tool_name:
            result = runtime.execute_tool(tool_name, payload)
            return jsonify(result)

        if prompt:
            result = runtime.execute_turn(prompt)
            return jsonify(
                {
                    "output": result.output,
                    "matched_tools": result.matched_tools,
                    "matched_commands": result.matched_commands,
                    "tool_results": result.tool_results,
                    "stop_reason": result.stop_reason,
                }
            )

        return jsonify({"error": "prompt or tool required"}), 400

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/tools", methods=["GET"])
def list_agent_tools():
    """List available agent tools."""
    if not hasattr(g, "user") or not g.user:
        return jsonify({"error": "Authentication required"}), 401

    try:
        from . import build_agent_runtime

        runtime = build_agent_runtime(user_id=g.user.id)
        tools = runtime.get_available_tools()

        return jsonify(
            {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "category": t.category,
                        "is_read_only": t.is_read_only,
                        "required_permissions": t.required_permissions,
                    }
                    for t in tools
                ]
            }
        )

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        return jsonify({"error": str(e)}), 500
