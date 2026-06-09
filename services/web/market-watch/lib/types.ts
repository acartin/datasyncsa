export type Role = "client-admin" | "client-viewer" | "system-admin" | "system-user";

export type MenuItem = {
  id: string;
  label: string;
  href: string;
  description: string;
};

export type MenuSection = {
  id: string;
  label: string;
  items: MenuItem[];
};

export type MenuPayload = {
  user: {
    id: string;
    email: string;
    role: Role;
    role_label: string;
  };
  tenant: {
    client_id: string;
    name: string;
    mode: string;
  };
  auth: {
    provider: string;
    status: string;
    can_simulate_roles?: boolean;
    is_role_simulated?: boolean;
  };
  sections: MenuSection[];
};

export type ModulePayload = {
  module: {
    id: string;
    title: string;
    description: string;
    status: string;
  };
  context: {
    client_id: string;
    role: Role;
  };
  links: Record<string, string>;
  actions: Array<Record<string, unknown>>;
  records: Array<Record<string, unknown>>;
};

export type CampaignWorkspaceSection = {
  id: string;
  label: string;
  description: string;
  records: Array<Record<string, unknown>>;
};

export type CampaignWorkspacePayload = {
  context: {
    client_id: string;
    role: Role;
    can_manage_access?: boolean;
  };
  campaign: Record<string, unknown>;
  available_clients?: Array<Record<string, unknown>>;
  available_chains?: Array<Record<string, unknown>>;
  available_stores?: Array<Record<string, unknown>>;
  available_products?: Array<Record<string, unknown>>;
  summary: Record<string, number>;
  sections: CampaignWorkspaceSection[];
};
