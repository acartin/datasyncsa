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
