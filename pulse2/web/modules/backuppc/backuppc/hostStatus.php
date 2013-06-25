<?php
/**
 * (c) 2004-2007 Linbox / Free&ALter Soft, http://linbox.com
 * (c) 2007-2008 Mandriva, http://www.mandriva.com
 *
 * $Id$
 *
 * This file is part of Mandriva Management Console (MMC).
 *
 * MMC is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * MMC is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with MMC; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 */

require("graph/navbar.inc.php");
require("localSidebar.php");
require_once("modules/backuppc/includes/xmlrpc.php");

$computer_name = $_GET['cn'];
$uuid = $_GET['objectUUID'];

/*
 * Display right top shortcuts menu
 */
right_top_shortcuts_display();

// Tab generator
$p = new TabbedPageGenerator();
$p->addTop(sprintf(_T("%s's backup status", 'backuppc'),$computer_name), "modules/backuppc/backuppc/header.php");

// Adding tabs
$p->addTab("tab1", _T('Summary', 'backuppc'), "", "modules/backuppc/backuppc/hostSummary.php", array('objectUUID'=>$uuid, 'cn'=>$computer_name));
$p->addTab("tab2", _T('Configuration', 'backuppc'), "", "modules/backuppc/backuppc/edit.php", array('objectUUID'=>$uuid, 'cn'=>$computer_name));

$p->setSideMenu($sidemenu);
$p->display();

?>