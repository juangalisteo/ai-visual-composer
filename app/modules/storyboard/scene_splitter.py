import re


class SceneSplitter:

    def split(
        self,
        text,
        scene_count
    ):
        text = str(
            text
        ).strip()

        if not text:
            return []

        scene_count = max(
            1,
            int(scene_count)
        )

        sentences = self._split_sentences(
            text
        )

        if not sentences:
            return []

        if scene_count <= 1:
            return [
                " ".join(
                    sentences
                ).strip()
            ]

        if len(sentences) >= scene_count:
            return self._partition_sentences(
                sentences=sentences,
                scene_count=scene_count
            )

        return self._partition_words(
            text=text,
            scene_count=scene_count
        )

    def _partition_sentences(
        self,
        sentences,
        scene_count
    ):
        sentence_weights = [
            max(
                1,
                len(sentence.split())
            )
            for sentence in sentences
        ]

        total_words = sum(
            sentence_weights
        )

        target_words = (
            total_words
            / scene_count
        )

        scenes = []
        current_sentences = []
        current_words = 0

        remaining_words = total_words
        remaining_scenes = scene_count

        for index, sentence in enumerate(
            sentences
        ):
            sentence_words = (
                sentence_weights[index]
            )

            sentences_left = (
                len(sentences) - index
            )

            must_close_scene = (
                sentences_left
                == remaining_scenes
            )

            candidate_words = (
                current_words
                + sentence_words
            )

            if (
                current_sentences
                and remaining_scenes > 1
                and (
                    candidate_words > target_words
                    or must_close_scene
                )
            ):
                distance_without = abs(
                    current_words
                    - target_words
                )

                distance_with = abs(
                    candidate_words
                    - target_words
                )

                if (
                    distance_without <= distance_with
                    or must_close_scene
                ):
                    scenes.append(
                        " ".join(
                            current_sentences
                        ).strip()
                    )

                    remaining_words -= (
                        current_words
                    )

                    remaining_scenes -= 1

                    target_words = (
                        remaining_words
                        / remaining_scenes
                    )

                    current_sentences = []
                    current_words = 0

            current_sentences.append(
                sentence
            )

            current_words += (
                sentence_words
            )

        if current_sentences:
            scenes.append(
                " ".join(
                    current_sentences
                ).strip()
            )

        while (
            len(scenes) < scene_count
            and scenes
        ):
            largest_index = max(
                range(len(scenes)),
                key=lambda index: len(
                    scenes[index].split()
                )
            )

            split_result = (
                self._split_scene_in_half(
                    scenes[largest_index]
                )
            )

            if split_result is None:
                break

            first_half, second_half = (
                split_result
            )

            scenes[largest_index] = (
                first_half
            )

            scenes.insert(
                largest_index + 1,
                second_half
            )

        return [
            scene.strip()
            for scene in scenes
            if scene.strip()
        ]

    def _partition_words(
        self,
        text,
        scene_count
    ):
        words = text.split()

        if not words:
            return []

        scene_count = min(
            scene_count,
            len(words)
        )

        base_size = (
            len(words)
            // scene_count
        )

        remainder = (
            len(words)
            % scene_count
        )

        scenes = []
        start_index = 0

        for index in range(
            scene_count
        ):
            current_size = (
                base_size
                + (
                    1
                    if index < remainder
                    else 0
                )
            )

            end_index = (
                start_index
                + current_size
            )

            scene_text = " ".join(
                words[start_index:end_index]
            ).strip()

            if scene_text:
                scenes.append(
                    scene_text
                )

            start_index = end_index

        return scenes

    def _split_scene_in_half(
        self,
        text
    ):
        sentences = self._split_sentences(
            text
        )

        if len(sentences) >= 2:
            total_words = sum(
                len(sentence.split())
                for sentence in sentences
            )

            target = (
                total_words / 2
            )

            first_part = []
            first_words = 0

            for sentence in sentences:
                sentence_words = len(
                    sentence.split()
                )

                if (
                    first_part
                    and first_words
                    + sentence_words
                    > target
                ):
                    break

                first_part.append(
                    sentence
                )

                first_words += (
                    sentence_words
                )

            split_index = len(
                first_part
            )

            second_part = (
                sentences[split_index:]
            )

            if first_part and second_part:
                return (
                    " ".join(
                        first_part
                    ).strip(),
                    " ".join(
                        second_part
                    ).strip()
                )

        words = text.split()

        if len(words) < 2:
            return None

        middle = (
            len(words) // 2
        )

        return (
            " ".join(
                words[:middle]
            ).strip(),
            " ".join(
                words[middle:]
            ).strip()
        )

    def _split_sentences(
        self,
        text
    ):
        parts = re.split(
            r"(?<=[.!?])\s+",
            text
        )

        return [
            part.strip()
            for part in parts
            if part.strip()
        ]