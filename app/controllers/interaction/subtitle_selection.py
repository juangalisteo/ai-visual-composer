"""Selección de configuraciones y perfiles de subtítulos independiente."""

from app.controllers.interaction import labels
from app.modules.studio import StudioInputMode
from app.shared.profile_identity import ProfileComponent


class SubtitleSelection:
    """Compone la selección declarativa de subtítulos sobre un resolver."""

    def __init__(self, subtitle_profile_resolver, terminal, on_cancel):
        self._subtitle_profile_resolver = subtitle_profile_resolver
        self._terminal = terminal
        self._on_cancel = on_cancel

    def _write(self, message, writer):
        (writer or self._terminal.write)(message)

    def _select(self, items, selector):
        if selector is not None:
            return selector(items)
        return self._terminal.select_from_list(items, self._on_cancel)

    def select_subtitle_config(
        self,
        profile_key=None,
        writer=None,
        selector=None,
        subtitle_label=None,
        select_subtitle_profile=None,
    ):
        if profile_key is not None:
            select_subtitle_profile = (
                select_subtitle_profile or self.select_subtitle_profile
            )
            return select_subtitle_profile(profile_key, "\nSUBTÍTULOS\n")

        configs = (
            "single_line",
            "word_by_word",
        )
        subtitle_label = subtitle_label or labels.subtitle_label
        self._write("\nSUBTÍTULOS\n", writer)
        for index, config in enumerate(configs, start=1):
            self._write(f"{index}. {subtitle_label(config)}", writer)
        return self._select(configs, selector)

    def select_profile_subtitle_config(
        self,
        profile_key,
        subtitle_profile_key=None,
        select_subtitle_config=None,
    ):
        if subtitle_profile_key is not None:
            return subtitle_profile_key
        select_subtitle_config = (
            select_subtitle_config or self.select_subtitle_config
        )
        return select_subtitle_config(profile_key)

    def select_studio_subtitle_config(
        self,
        profile_key,
        select_subtitle_profile=None,
    ):
        select_subtitle_profile = (
            select_subtitle_profile or self.select_subtitle_profile
        )
        return select_subtitle_profile(profile_key, "\nSUBTITULOS\n")

    def select_studio_subtitle_options(
        self,
        profile_key,
        input_mode,
        writer=None,
        selector=None,
        select_srt_video_subtitle_options=None,
    ):
        if input_mode == StudioInputMode.SRT_VIDEO.value:
            select_srt_video_subtitle_options = (
                select_srt_video_subtitle_options
                or self.select_studio_srt_video_subtitle_options
            )
            return select_srt_video_subtitle_options(profile_key)

        descriptors = self._subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        selections = tuple(
            descriptor.profile_id
            for descriptor in descriptors
        )
        self._write("\nSUBTÍTULOS\n", writer)
        for index, selection in enumerate(selections, start=1):
            label = next(
                descriptor.display_name
                for descriptor in descriptors
                if descriptor.profile_id == selection
            )
            self._write(f"{index}. {label}", writer)
        selection = self._select(selections, selector)
        return selection, False

    def select_studio_srt_video_subtitle_options(
        self,
        profile_key,
        writer=None,
        selector=None,
    ):
        descriptors = self._subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        selections = tuple(descriptors)
        self._write("\nSUBTÍTULOS\n", writer)
        for index, descriptor in enumerate(descriptors, start=1):
            self._write(f"{index}. {descriptor.display_name}", writer)
        selection = self._select(selections, selector)
        return selection.key, True

    def select_subtitle_profile(
        self,
        profile_key,
        heading,
        writer=None,
        selector=None,
    ):
        descriptors = self._subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        selections = tuple(
            descriptor.profile_id
            for descriptor in descriptors
        )
        self._write(heading, writer)
        for index, descriptor in enumerate(descriptors, start=1):
            self._write(f"{index}. {descriptor.display_name}", writer)
        return self._select(selections, selector)

    def select_profile_subtitle_profile(
        self,
        component,
        platform,
        writer=None,
        selector=None,
        family_label=None,
        presentation_families=None,
    ):
        family_label = family_label or labels.family_label
        presentation_families = (
            presentation_families or labels.presentation_families
        )
        families = presentation_families(
            self._subtitle_profile_resolver.discover_families(component, platform),
        )
        if not families:
            raise FileNotFoundError(
                "No hay familias de subtitulos para la plataforma "
                f"{platform}."
            )
        self._write("\nSUBTÍTULOS\n", writer)
        self._write("FAMILIA\n", writer)
        for index, family in enumerate(families, start=1):
            self._write(f"{index}. {family_label(family)}", writer)
        family = self._select(families, selector)
        profiles = self._subtitle_profile_resolver.discover_profiles_for_family(
            component,
            platform,
            family,
        )
        self._write("\nPERFIL\n", writer)
        for index, descriptor in enumerate(profiles, start=1):
            self._write(f"{index}. {descriptor.display_name}", writer)
        return self._select(profiles, selector).key

    def select_studio_subtitle_profile(
        self,
        input_mode,
        platform=None,
        writer=None,
        selector=None,
        label=None,
        family_label=None,
        presentation_families=None,
    ):
        component = ProfileComponent.STUDIO
        label = label or labels.label
        family_label = family_label or labels.family_label
        presentation_families = (
            presentation_families or labels.presentation_families
        )
        if platform is None:
            self._write("\nPLATAFORMA\n", writer)
            platforms = self._subtitle_profile_resolver.discover_platforms(component)
            if not platforms:
                raise FileNotFoundError(
                    "No hay perfiles de subtitulos STUDIO disponibles."
                )
            for index, candidate in enumerate(platforms, start=1):
                self._write(f"{index}. {label(candidate)}", writer)
            platform = self._select(platforms, selector)

        self._write("\nSUBTÍTULOS\n", writer)
        self._write("FAMILIA\n", writer)
        families = presentation_families(
            self._subtitle_profile_resolver.discover_families(component, platform),
        )
        for index, family in enumerate(families, start=1):
            self._write(f"{index}. {family_label(family)}", writer)
        family = self._select(families, selector)
        descriptors = self._subtitle_profile_resolver.discover_profiles_for_family(
            component,
            platform,
            family,
        )
        selections = list(descriptors)
        self._write("\nPERFIL\n", writer)
        for index, selection in enumerate(selections, start=1):
            self._write(f"{index}. {selection.display_name}", writer)
        selection = self._select(tuple(selections), selector)
        return (
            selection.key,
            input_mode == StudioInputMode.SRT_VIDEO.value,
        )

    def select_studio_video_audio_srt_subtitle_profile(
        self,
        profile_key,
        writer=None,
        selector=None,
        family_label=None,
        presentation_families=None,
    ):
        component = ProfileComponent.STUDIO
        platform = profile_key.platform
        family_label = family_label or labels.family_label
        presentation_families = (
            presentation_families or labels.presentation_families
        )
        self._write("\nFAMILIA\n", writer)
        families = presentation_families(
            self._subtitle_profile_resolver.discover_families(
                component,
                platform,
            ),
        )
        if not families:
            raise FileNotFoundError(
                "No hay familias de subtitulos STUDIO para la plataforma "
                f"{platform}."
            )
        for index, family in enumerate(families, start=1):
            self._write(f"{index}. {family_label(family)}", writer)
        family = self._select(families, selector)
        descriptors = self._subtitle_profile_resolver.discover_profiles_for_family(
            component,
            platform,
            family,
        )
        if not descriptors:
            raise FileNotFoundError(
                "No hay perfiles de subtitulos STUDIO para la familia "
                f"{family}."
            )
        self._write("\nPERFIL\n", writer)
        for index, descriptor in enumerate(descriptors, start=1):
            self._write(f"{index}. {descriptor.display_name}", writer)
        return self._select(descriptors, selector).key
