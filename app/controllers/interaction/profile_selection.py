"""Selección operacional de perfiles STUDIO independiente del controlador."""

from app.shared.profile_identity import ProfileComponent


class ProfileSelection:
    """Descubre y selecciona perfiles operacionales de STUDIO."""

    def __init__(
        self,
        profile_resolver,
        studio_profile_loader,
        terminal,
        on_cancel,
    ):
        self._profile_resolver = profile_resolver
        self._studio_profile_loader = studio_profile_loader
        self._terminal = terminal
        self._on_cancel = on_cancel

    def _write(self, message, writer):
        (writer or self._terminal.write)(message)

    def _select(self, items, selector):
        if selector is not None:
            return selector(items)
        return self._terminal.select_from_list(items, self._on_cancel)

    def studio_operational_profiles_by_format(self):
        component = ProfileComponent.STUDIO
        profiles_by_format = {}
        for profile_format in self._profile_resolver.discover_formats(component):
            descriptors = self._profile_resolver.discover_operational_profiles(
                component,
                profile_format,
            )
            if descriptors:
                profiles_by_format[profile_format] = descriptors
        return profiles_by_format

    def select_profile_identity(
        self,
        component,
        writer=None,
        selector=None,
        label=None,
    ):
        profiles_by_format = {}
        for profile_format in self._profile_resolver.discover_formats(component):
            descriptors = self._profile_resolver.discover_operational_profiles(
                component,
                profile_format,
            )
            if descriptors:
                profiles_by_format[profile_format] = descriptors

        profile_formats = tuple(sorted(profiles_by_format))
        if not profile_formats:
            raise FileNotFoundError(
                "No hay perfiles operacionales validos para el componente "
                "seleccionado."
            )
        label = label or (lambda value: value)
        self._write("\nPLATAFORMA\n", writer)
        for index, profile_format in enumerate(profile_formats, start=1):
            self._write(f"{index}. {label(profile_format)}", writer)
        profile_format = self._select(profile_formats, selector)

        descriptors = profiles_by_format[profile_format]
        if len(descriptors) == 1:
            profile_key = descriptors[0].key
        else:
            self._write("\nPERFIL OPERACIONAL\n", writer)
            for index, descriptor in enumerate(descriptors, start=1):
                self._write(f"{index}. {descriptor.display_name}", writer)
            profile_key = self._select(descriptors, selector).key
        return {
            "path": self._profile_resolver.resolve_operational(profile_key),
            "profile_key": profile_key,
        }

    def select_studio_operational_format(
        self,
        profiles_by_format,
        writer=None,
        selector=None,
        label=None,
    ):
        profile_formats = tuple(sorted(profiles_by_format))
        if not profile_formats:
            raise FileNotFoundError(
                "No hay perfiles operacionales STUDIO disponibles."
            )
        label = label or (lambda value: value)
        self._write("\nPLATAFORMA\n", writer)
        for index, profile_format in enumerate(profile_formats, start=1):
            self._write(f"{index}. {label(profile_format)}", writer)
        return self._select(profile_formats, selector)

    def select_studio_operational_profile(
        self,
        profile_format=None,
        profiles_by_format=None,
        profiles_by_format_provider=None,
        select_format=None,
        writer=None,
        selector=None,
    ):
        profiles_by_format = (
            profiles_by_format
            if profiles_by_format is not None
            else (profiles_by_format_provider or self.studio_operational_profiles_by_format)()
        )
        if profile_format is None:
            select_format = (
                select_format or self.select_studio_operational_format
            )
            profile_format = select_format(profiles_by_format)

        if profile_format not in profiles_by_format:
            raise FileNotFoundError(
                "No hay perfiles operacionales STUDIO para la plataforma "
                f"{profile_format}."
            )
        descriptors = profiles_by_format[profile_format]
        if len(descriptors) == 1:
            profile_key = descriptors[0].key
        else:
            self._write("\nPERFIL OPERACIONAL\n", writer)
            for index, descriptor in enumerate(descriptors, start=1):
                self._write(f"{index}. {descriptor.display_name}", writer)
            profile_key = self._select(descriptors, selector).key
        return (
            profile_key,
            self._studio_profile_loader.load(
                self._profile_resolver.load_operational(profile_key),
                profile_key,
            ),
        )
