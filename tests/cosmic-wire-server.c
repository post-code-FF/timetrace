/* Minimal protocol fixture: uses the upstream generated server interfaces,
 * deliberately sends COSMIC state before ext-list metadata done. */
#include <stdint.h>
#include <wayland-server.h>
#include "cosmic-toplevel-info-unstable-v1.h"
#include "ext-foreign-toplevel-list-v1.h"
#include "kde-idle.h"

static struct wl_display *display;
static struct wl_resource *info, *foreign, *cosmic;
static struct wl_event_source *timer;

static void destroy(struct wl_client *client, struct wl_resource *resource) {
    (void)client;
    wl_resource_destroy(resource);
}
static void stop(struct wl_client *client, struct wl_resource *resource) {
    (void)client; (void)resource;
}
static const struct ext_foreign_toplevel_handle_v1_interface foreign_impl = { .destroy = destroy };
static const struct zcosmic_toplevel_handle_v1_interface cosmic_impl = { .destroy = destroy };
static const struct ext_foreign_toplevel_list_v1_interface list_impl = { .stop = stop, .destroy = destroy };

static int change_focus(void *data) {
    (void)data;
    struct wl_array empty;
    wl_array_init(&empty);
    zcosmic_toplevel_handle_v1_send_state(cosmic, &empty);
    ext_foreign_toplevel_handle_v1_send_title(foreign, "Changed before state commit");
    ext_foreign_toplevel_handle_v1_send_done(foreign);
    zcosmic_toplevel_info_v1_send_done(info);
    wl_display_flush_clients(display);
    return 0;
}
static void get_cosmic(struct wl_client *client, struct wl_resource *resource,
                       uint32_t id, struct wl_resource *handle) {
    (void)handle;
    cosmic = wl_resource_create(client, &zcosmic_toplevel_handle_v1_interface, 2, id);
    wl_resource_set_implementation(cosmic, &cosmic_impl, NULL, NULL);
    struct wl_array states;
    wl_array_init(&states);
    uint32_t *values = wl_array_add(&states, 2 * sizeof(uint32_t));
    values[0] = ZCOSMIC_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED;
    values[1] = ZCOSMIC_TOPLEVEL_HANDLE_V1_STATE_FULLSCREEN;
    zcosmic_toplevel_handle_v1_send_state(cosmic, &states);
    zcosmic_toplevel_info_v1_send_done(resource);
    wl_array_release(&states);
    timer = wl_event_loop_add_timer(wl_display_get_event_loop(display), change_focus, NULL);
    wl_event_source_timer_update(timer, 250);
}
static const struct zcosmic_toplevel_info_v1_interface info_impl = {
    .stop = stop, .get_cosmic_toplevel = get_cosmic,
};
static void bind_info(struct wl_client *client, void *data, uint32_t version, uint32_t id) {
    (void)data;
    info = wl_resource_create(client, &zcosmic_toplevel_info_v1_interface, version, id);
    wl_resource_set_implementation(info, &info_impl, NULL, NULL);
}
static void bind_list(struct wl_client *client, void *data, uint32_t version, uint32_t id) {
    (void)data;
    struct wl_resource *manager = wl_resource_create(client, &ext_foreign_toplevel_list_v1_interface, version, id);
    wl_resource_set_implementation(manager, &list_impl, NULL, NULL);
    foreign = wl_resource_create(client, &ext_foreign_toplevel_handle_v1_interface, 1, 0);
    wl_resource_set_implementation(foreign, &foreign_impl, NULL, NULL);
    ext_foreign_toplevel_list_v1_send_toplevel(manager, foreign);
    ext_foreign_toplevel_handle_v1_send_app_id(foreign, "org.timetrace.CosmicFixture");
    ext_foreign_toplevel_handle_v1_send_title(foreign, "COSMIC initial");
    ext_foreign_toplevel_handle_v1_send_done(foreign);
}

static struct wl_resource *idle_timeout;
static int resume_idle(void *data) {
    (void)data;
    org_kde_kwin_idle_timeout_send_resumed(idle_timeout);
    return 0;
}
static const struct org_kde_kwin_idle_timeout_interface timeout_impl = { .release = destroy };
static void get_idle(struct wl_client *client, struct wl_resource *resource,
                     uint32_t id, struct wl_resource *seat, uint32_t timeout) {
    (void)resource; (void)seat; (void)timeout;
    idle_timeout = wl_resource_create(client, &org_kde_kwin_idle_timeout_interface, 1, id);
    wl_resource_set_implementation(idle_timeout, &timeout_impl, NULL, NULL);
    org_kde_kwin_idle_timeout_send_idle(idle_timeout);
    struct wl_event_source *resume = wl_event_loop_add_timer(wl_display_get_event_loop(display), resume_idle, NULL);
    wl_event_source_timer_update(resume, 80);
}
static const struct org_kde_kwin_idle_interface idle_impl = { .get_idle_timeout = get_idle };
static void bind_idle(struct wl_client *client, void *data, uint32_t version, uint32_t id) {
    (void)data;
    struct wl_resource *resource = wl_resource_create(client, &org_kde_kwin_idle_interface, version, id);
    wl_resource_set_implementation(resource, &idle_impl, NULL, NULL);
}
static void bind_seat(struct wl_client *client, void *data, uint32_t version, uint32_t id) {
    (void)data;
    struct wl_resource *resource = wl_resource_create(client, &wl_seat_interface, version, id);
    wl_resource_set_implementation(resource, NULL, NULL, NULL);
    wl_seat_send_capabilities(resource, 0);
}

int main(void) {
    display = wl_display_create();
    if (!display || wl_display_add_socket(display, "cosmic-test") < 0) return 1;
    wl_global_create(display, &zcosmic_toplevel_info_v1_interface, 2, NULL, bind_info);
    wl_global_create(display, &ext_foreign_toplevel_list_v1_interface, 1, NULL, bind_list);
    wl_global_create(display, &org_kde_kwin_idle_interface, 1, NULL, bind_idle);
    wl_global_create(display, &wl_seat_interface, 1, NULL, bind_seat);
    wl_display_run(display);
    return 0;
}
