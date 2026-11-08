import { KycRole } from "@/lib/api";

/** Post-login destination per role; unauthorised roles get null (stay put). */
export function workspaceDestinationFor(role: KycRole): string | null {
  switch (role) {
    case "CUSTOMER":
      return "/orders";
    case "OPERATIONS":
      return "/operations";
    case "PARTNER":
      return "/partner";
    case "REVIEWER":
      return "/kyc";
    default:
      return null;
  }
}

const ROLE_ROUTE_PREFIXES: Record<KycRole, string[]> = {
  CUSTOMER: ["/orders", "/kyc", "/get-started"],
  REVIEWER: ["/kyc"],
  OPERATIONS: ["/operations"],
  PARTNER: ["/partner"],
};

/** Is `role` authorised to view `pathname`? Used to validate intended
 * destinations before preserving them across login. */
export function isRoleAuthorisedFor(role: KycRole, pathname: string): boolean {
  const prefixes = ROLE_ROUTE_PREFIXES[role];
  return Boolean(prefixes?.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)));
}
