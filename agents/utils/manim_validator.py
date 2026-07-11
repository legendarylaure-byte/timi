import ast
import logging

logger = logging.getLogger(__name__)


def validate_manim_code(code: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    scene_class: str | None = None

    # Stage 1: Syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"valid": False, "errors": [f"Syntax error: {e}"], "warnings": [], "scene_class": None}

    # Stage 2: Structure — find a Scene or ThreeDScene subclass
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in ("Scene", "ThreeDScene"):
                    scene_class = node.name
                    break
    if not scene_class:
        errors.append("No class inheriting from Scene or ThreeDScene found")

    # Stage 3: construct method on the scene class
    if scene_class:
        cls_node = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == scene_class),
            None,
        )
        if cls_node:
            has_construct = any(
                isinstance(item, ast.FunctionDef) and item.name == "construct"
                for item in cls_node.body
            )
            if not has_construct:
                errors.append(f"Class '{scene_class}' has no 'construct' method")

    # Stage 4: At least one animation action (self.play / self.add / self.wait)
    has_action = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                # Check self.play, self.add, self.wait, self.remove, self.clear
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                    if attr_name in ("play", "add", "wait", "remove", "clear"):
                        has_action = True
                        break
                # Handle chained calls like self.camera.frame.animate (should not match)
                if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "self":
                    if attr_name in ("play", "add", "wait", "remove", "clear"):
                        has_action = True
                        break
    if not has_action:
        warnings.append("No self.play/self.add/self.wait calls found in construct method")

    # Stage 5: Safety blocklist
    dangerous_patterns = ["os.system", "subprocess.", "eval(", "exec(", "__import__"]
    for pattern in dangerous_patterns:
        if pattern in code:
            errors.append(f"Blocked unsafe call: '{pattern}' used in code")

    # Stage 6: Compile check
    try:
        compile(code, "<manim_validation>", "exec")
    except Exception as e:
        errors.append(f"Compile-time error: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "scene_class": scene_class,
    }
