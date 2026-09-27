"""Topic taxonomy shared by the server (keyword fallback) and the LLM classifier."""

TOPICS = {
    "Robot Navigation":        ["navigation", "path planning", "mobile robot", "localization", "mapping", "slam"],
    "Autonomous Driving":      ["autonomous driving", "self-driving", "vehicle", "traffic", "waymo", "nuplan", "carla"],
    "Reinforcement Learning":  ["reinforcement learning", " rl ", "policy", "reward", "q-learning", "actor-critic", "ppo", "sac"],
    "Video Generation":        ["video generation", "video prediction", "future frame", "video diffusion", "video synthesis"],
    "3D Scene Modeling":       ["nerf", "3d scene", "scene reconstruction", "point cloud", "occupancy", "gaussian splatting"],
    "Physics & Dynamics":      ["physics", "dynamics", "rigid body", "fluid", "contact", "mujoco", "isaac"],
    "Planning & Control":      ["planning", "model predictive", "mpc", "tree search", "mcts", "decision making"],
    "Language & Vision":       ["vision-language", "vlm", "multimodal", "language model", "llm", "gpt", "clip"],
    "Situational Awareness":   ["situational awareness", "scene understanding", "anomaly", "uncertainty", "safety"],
    "Game Playing":            ["atari", "minecraft", "chess", "dota", "starcraft", "game environment"],
    "Robotics & Manipulation": ["manipulation", "grasping", "dexterous", "humanoid", "end-effector"],
    "Latent Space Models":     ["latent", "vae", "encoder", "representation learning", "dreamer", "rssm"],
}


def assign_topics(title: str, abstract: str):
    text = (title + " " + abstract).lower()
    matched = [t for t, kws in TOPICS.items() if any(k in text for k in kws)]
    return matched or ["Other"]
