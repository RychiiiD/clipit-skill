"""clipit — semantic topic-based video rough-cut tool."""

__version__ = "0.1.0"


class Clipit:
    """High-level SDK for clipit operations.

    Usage:
        c = Clipit()
        transcript = c.transcribe("video.mp4")
        decisions = [...]  # from Agent's LLM
        result = c.splice("video.mp4", decisions)       # single video
        result = c.splice(["v1.mp4", "v2.mp4"], decisions)  # multi-video
    """

    def transcribe(self, video_path: str, model_name: str = "small") -> dict:
        from .transcribe import transcribe
        return transcribe(video_path, model_name)

    def splice(self, video_paths, decisions: list, output_path: str = None) -> str:
        from .splice import splice
        return splice(video_paths, decisions, output_path)

    def check(self) -> dict:
        from .install import check_env
        return check_env()

    def clean(self, input_path: str, output_path: str = None) -> dict:
        from .clean import clean_transcript
        return clean_transcript(input_path, output_path)

    def validate(self, input_path: str, output_path: str = None, intensity: str = "medium") -> dict:
        from .validate import validate_file
        return validate_file(input_path, output_path, intensity=intensity)
