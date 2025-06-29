class tags:
    def __init__(self):
        self.tag_index = []
    
    def reset_tags(self):
        self.tag_index = []

    def process(self, a):
        self.reset_tags()

        if isinstance(a, str):
            parts = a.split()
            if not parts:
                return

            # First part is command - append as-is (lowercase to keep consistent)
            self.tag_index.append(parts[0].lower())

            # Process the rest
            for part in parts[1:]:
                part = part.strip()
                # If part is quoted, strip quotes and keep as string
                if (part.startswith("'") and part.endswith("'")) or (part.startswith('"') and part.endswith('"')):
                    self.tag_index.append(part[1:-1])
                else:
                    # Try int, float, or else keep as string (lowercase)
                    if part.isdigit():
                        self.tag_index.append(int(part))
                    else:
                        try:
                            self.tag_index.append(float(part))
                        except ValueError:
                            self.tag_index.append(part.lower())
        else:
            self.tag_index.append(a)

    def __repr__(self):
        return repr(self.tag_index)
