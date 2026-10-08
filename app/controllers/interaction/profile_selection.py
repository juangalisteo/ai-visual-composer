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

    def studio_operational_profiles_by_platform(self):
        component = ProfileComponent.STUDIO
        profiles_by_platform = {}
        for platform in self._profile_resolver.discover_platforms(component):
            descriptors = self._profile_resolver.discover_operational_profiles(
                component,
                platform,
            )
            if descriptors:
                profiles_by_platform[platform] = descriptors
        return profiles_by_platform

    def select_profile_identity(
        self,
        component,
        writer=None,
        selector=None,
        label=None,
    ):
        profiles_by_platform = {}
        for platform in self._profile_resolver.discover_platforms(component):
            descriptors = self._profile_resolver.discover_operational_profiles(
                component,
                platform,
            )
            if descriptors:
                profiles_by_platform[platform] = descriptors

        platforms = tuple(sorted(profiles_by_platform))
        if not platforms:
            raise FileNotFoundError(
                "No hay perfiles operacionales validos para el componente "
                "seleccionado."
            )
        label = label or (lambda value: value)
        self._write("\nPLATAFORMA\n", writer)
        for index, platform in enumerate(platforms, start=1):
            self._write(f"{index}. {label(platform)}", writer)
        platform = self._select(platforms, selector)

        descriptors = profiles_by_platform[platform]
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

    def select_studio_operational_platform(
        self,
        profiles_by_platform,
        writer=None,
        selector=None,
        label=None,
    ):
        platforms = tuple(sorted(profiles_by_platform))
        if not platforms:
            raise FileNotFoundError(
                "No hay perfiles operacionales STUDIO disponibles."
            )
        label = label or (lambda value: value)
        self._write("\nPLATAFORMA\n", writer)
        for index, platform in enumerate(platforms, start=1):
            self._write(f"{index}. {label(platform)}", writer)
        return self._select(platforms, selector)

    def select_studio_operational_profile(
        self,
        platform=None,
        profiles_by_platform=None,
        profiles_by_platform_provider=None,
        select_platform=None,
        writer=None,
        selector=None,
    ):
        profiles_by_platform = (
            profiles_by_platform
            if profiles_by_platform is not None
            else (profiles_by_platform_provider or self.studio_operational_profiles_by_platform)()
        )
        if platform is None:
            select_platform = (
                select_platform or self.select_studio_operational_platform
            )
            platform = select_platform(profiles_by_platform)

        if platform not in profiles_by_platform:
            raise FileNotFoundError(
                "No hay perfiles operacionales STUDIO para la plataforma "
                f"{platform}."
            )
        descriptors = profiles_by_platform[platform]
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
