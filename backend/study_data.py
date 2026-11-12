EXAMPLE_NOTES = [
    ("Python basics", "Python", "Python uses indentation to group code. Start with variables, lists, loops, and functions.\n\nExample: for number in range(3) runs a loop for 0, 1, and 2."),
    ("Docker", "Docker", "An image is the blueprint for a container. A container is a running instance of that image.\n\nA Dockerfile describes how to build the image. Docker Compose starts multiple services together."),
    ("Kubernetes pods", "Kubernetes", "A pod is the smallest deployable unit in Kubernetes. Containers in the same pod share a network and can share volumes.\n\nA Deployment keeps the desired number of pods running. A Service gives those pods a stable address."),
    ("Machine learning basics", "AI", "A machine learning model learns patterns from examples. A spam filter can learn from messages labeled spam or legitimate.\n\nKeep some examples for testing so you can measure how well the model handles new data."),
]

RELATED = {
    "docker": [("Docker Compose", "Run multiple services together from one YAML file."), ("Kubernetes", "Learn how to manage containers across a cluster."), ("Container Networking", "See how containers communicate with each other.")],
    "kubernetes": [("Services", "Give a set of pods a stable network address."), ("Deployments", "Keep pods running and roll out new versions."), ("Persistent Volumes", "Store data across pod restarts.")],
    "python": [("Python Functions", "Group reusable steps into named functions."), ("FastAPI", "Build a small REST API in Python.")],
    "ai": [("Supervised Learning", "Train a model on labeled examples."), ("Model Evaluation", "Check how a model performs on new data.")],
}
