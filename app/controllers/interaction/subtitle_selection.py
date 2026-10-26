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

    def select_profile_subtitle_profile(
        self,
        component,
        profile_format,
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
            self._subtitle_profile_resolver.discover_families(component, profile_format),
        )
        if not families:
            raise FileNotFoundError(
                "No hay familias de subtítulos para el formato "
                f"{profile_format}."
            )
        self._write("\nSUBTÍTULOS\n", writer)
        self._write("FAMILIA\n", writer)
        for index, family in enumerate(families, start=1):
            self._write(f"{index}. {family_label(family)}", writer)
        family = self._select(families, selector)
        profiles = self._subtitle_profile_resolver.discover_profiles_for_family(
            component,
            profile_format,
            family,
        )
        self._write("\nPERFIL\n", writer)
        for index, descriptor in enumerate(profiles, start=1):
            self._write(f"{index}. {descriptor.display_name}", writer)
        return self._select(profiles, selector).key

    def select_studio_subtitle_profile(
        self,
        input_mode,
        profile_format=None,
        writer=None,
        selector=None,
        label=None,
        family_label=None,
        presentation_families=None,
        order=None,
    ):
        component = ProfileComponent.STUDIO
        label = label or labels.label
        family_label = family_label or labels.family_label
        presentation_families = (
            presentation_families or labels.presentation_families
        )
        if profile_format is None:
            self._write("\nFORMATO\n", writer)
            profile_formats = tuple((order or sorted)(
                self._subtitle_profile_resolver.discover_formats(component),
            ))
            if not profile_formats:
                raise FileNotFoundError(
                    "No hay perfiles de subtítulos STUDIO disponibles."
                )
            for index, candidate in enumerate(profile_formats, start=1):
                self._write(f"{index}. {label(candidate)}", writer)
            profile_format = self._select(profile_formats, selector)

        self._write("\nSUBTÍTULOS\n", writer)
        self._write("FAMILIA\n", writer)
        families = presentation_families(
            self._subtitle_profile_resolver.discover_families(component, profile_format),
        )
        for index, family in enumerate(families, start=1):
            self._write(f"{index}. {family_label(family)}", writer)
        family = self._select(families, selector)
        descriptors = self._subtitle_profile_resolver.discover_profiles_for_family(
            component,
            profile_format,
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
        profile_format = profile_key.format
        family_label = family_label or labels.family_label
        presentation_families = (
            presentation_families or labels.presentation_families
        )
        self._write("\nFAMILIA\n", writer)
        families = presentation_families(
            self._subtitle_profile_resolver.discover_families(
                component,
                profile_format,
            ),
        )
        if not families:
            raise FileNotFoundError(
                "No hay familias de subtítulos STUDIO para el formato "
                f"{profile_format}."
            )
        for index, family in enumerate(families, start=1):
            self._write(f"{index}. {family_label(family)}", writer)
        family = self._select(families, selector)
        descriptors = self._subtitle_profile_resolver.discover_profiles_for_family(
            component,
            profile_format,
            family,
        )
        if not descriptors:
            raise FileNotFoundError(
                "No hay perfiles de subtítulos STUDIO para la familia "
                f"{family}."
            )
        self._write("\nPERFIL\n", writer)
        for index, descriptor in enumerate(descriptors, start=1):
            self._write(f"{index}. {descriptor.display_name}", writer)
        return self._select(descriptors, selector).key
