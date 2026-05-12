// Minimal shim matching CRM's usersStore interface.
// Reads user info from window.frappe.boot.user_info which the CRM SPA populates.
export function usersStore() {
  function getUser(email) {
    const u = window.frappe?.boot?.user_info?.[email] || {}
    return {
      name: email,
      email: email,
      full_name:
        u.fullname || u.full_name || email?.split('@')[0] || email || '',
      first_name: email?.split('@')[0] || email || '',
      last_name: '',
      user_image: u.image || u.user_image || null,
      role: null,
    }
  }
  return { getUser }
}
