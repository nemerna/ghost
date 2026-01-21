/**
 * Main application layout with sidebar navigation
 */

import { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Avatar,
  Brand,
  Dropdown,
  DropdownItem,
  DropdownList,
  Masthead,
  MastheadBrand,
  MastheadContent,
  MastheadMain,
  MastheadToggle,
  MenuToggle,
  Nav,
  NavItem,
  NavList,
  Page,
  PageSidebar,
  PageSidebarBody,
  SkipToContent,
  Toolbar,
  ToolbarContent,
  ToolbarGroup,
  ToolbarItem,
} from '@patternfly/react-core';
import { BarsIcon } from '@patternfly/react-icons';
import { useAuth } from '@/auth';

interface NavItemDef {
  id: string;
  label: string;
  path: string;
  roles?: ('user' | 'manager' | 'admin')[];
}

const navItems: NavItemDef[] = [
  { id: 'dashboard', label: 'Dashboard', path: '/' },
  { id: 'activities', label: 'My Activities', path: '/activities' },
  { id: 'reports', label: 'My Reports', path: '/reports' },
  { id: 'team-dashboard', label: 'Team Dashboard', path: '/team', roles: ['manager', 'admin'] },
  { id: 'team-reports', label: 'Team Reports', path: '/team/reports', roles: ['manager', 'admin'] },
  { id: 'management-reports', label: 'Management Reports', path: '/management-reports', roles: ['manager', 'admin'] },
  { id: 'admin-users', label: 'User Management', path: '/admin/users', roles: ['admin'] },
  { id: 'admin-teams', label: 'Team Management', path: '/admin/teams', roles: ['admin'] },
];

export function AppLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // Filter nav items based on user role
  const visibleNavItems = navItems.filter((item) => {
    if (!item.roles) return true;
    return user && item.roles.includes(user.role);
  });

  const onNavSelect = (_event: React.FormEvent<HTMLInputElement>, result: { itemId: string | number }) => {
    const item = visibleNavItems.find((i) => i.id === result.itemId);
    if (item) {
      navigate(item.path);
    }
  };

  const getActiveItemId = () => {
    // Find the matching nav item for the current path
    const match = visibleNavItems.find((item) => {
      if (item.path === '/') {
        return location.pathname === '/';
      }
      return location.pathname.startsWith(item.path);
    });
    return match?.id || 'dashboard';
  };

  const userDropdownItems = (
    <DropdownList>
      <DropdownItem key="settings" onClick={() => navigate('/settings')}>
        Settings
      </DropdownItem>
      <DropdownItem key="role" isDisabled>
        Role: {user?.role || 'user'}
      </DropdownItem>
    </DropdownList>
  );

  const headerToolbar = (
    <Toolbar id="header-toolbar" isFullHeight isStatic>
      <ToolbarContent>
        <ToolbarGroup
          variant="action-group-plain"
          align={{ default: 'alignEnd' }}
        >
          <ToolbarItem>
            <Dropdown
              isOpen={isUserMenuOpen}
              onSelect={() => setIsUserMenuOpen(false)}
              onOpenChange={(isOpen) => setIsUserMenuOpen(isOpen)}
              toggle={(toggleRef) => (
                <MenuToggle
                  ref={toggleRef}
                  onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                  isFullHeight
                  isExpanded={isUserMenuOpen}
                  icon={
                    <Avatar
                      src=""
                      alt={user?.display_name || user?.email || 'User'}
                    />
                  }
                >
                  {user?.display_name || user?.email || 'User'}
                </MenuToggle>
              )}
            >
              {userDropdownItems}
            </Dropdown>
          </ToolbarItem>
        </ToolbarGroup>
      </ToolbarContent>
    </Toolbar>
  );

  const masthead = (
    <Masthead>
      <MastheadToggle>
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          aria-label="Toggle sidebar"
          className="pf-v6-c-button pf-m-plain"
        >
          <BarsIcon />
        </button>
      </MastheadToggle>
      <MastheadMain>
        <MastheadBrand>
          <Brand src="" alt="Jira MCP">
            <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>Jira MCP</span>
          </Brand>
        </MastheadBrand>
      </MastheadMain>
      <MastheadContent>{headerToolbar}</MastheadContent>
    </Masthead>
  );

  const navigation = (
    <Nav onSelect={onNavSelect} aria-label="Main navigation">
      <NavList>
        {visibleNavItems.map((item) => (
          <NavItem
            key={item.id}
            itemId={item.id}
            isActive={getActiveItemId() === item.id}
          >
            {item.label}
          </NavItem>
        ))}
      </NavList>
    </Nav>
  );

  const sidebar = (
    <PageSidebar isSidebarOpen={isSidebarOpen}>
      <PageSidebarBody>{navigation}</PageSidebarBody>
    </PageSidebar>
  );

  const skipToContent = (
    <SkipToContent href="#main-content">Skip to content</SkipToContent>
  );

  return (
    <Page
      masthead={masthead}
      sidebar={sidebar}
      skipToContent={skipToContent}
      mainContainerId="main-content"
    >
      <Outlet />
    </Page>
  );
}

export default AppLayout;
